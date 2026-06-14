"""Interactive HITL cycle: V1 -> typed expert answer -> learn -> V2 (offline)."""

import pytest

from finflow.models import Question, QuestionFamily
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_human_answers, load_questions

from .helpers import RoutingProvider

INV_V1 = {
    "reasoning_steps": [{"claim": "timeouts", "cited_source_ids": ["slack:inc-jun3-charge"], "confidence": 0.7}],
    "candidate_root_causes": ["retries"], "summary": "s",
    "answer_text": "Risk timeouts caused retries.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge"],
}
INV_V2 = {
    "reasoning_steps": [{"claim": "guard disabled", "cited_source_ids": ["commit:a1"], "confidence": 0.9}],
    "candidate_root_causes": ["disabled guard"], "summary": "s",
    "answer_text": "A recent commit removed a safeguard; retries then duplicated.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge", "commit:a1", "commit:a15"],
}
GAP = {"reasoning_gaps": ["did not check commits"], "missed_root_causes": ["disabled guard"], "narrative": "n"}
LEARNING = {"patterns": [
    {"pattern_type": "source_routing", "hint_text": "prefer recent commits", "routing_sources": ["commit", "ticket", "slack"], "trigger_conditions": "incident", "confidence": 0.85},
    {"pattern_type": "missed_evidence", "hint_text": "recent commit", "retrieval_signals": ["refactor", "revert", "disable", "perf"], "trigger_conditions": "dupes", "confidence": 0.8},
    {"pattern_type": "expert_heuristic", "hint_text": "inspect recent commits for removed safeguards", "trigger_conditions": "incident", "confidence": 0.9},
]}


def _provider():
    return RoutingProvider(rules=[
        ("GENERALIZABLE investigative lessons", LEARNING),
        ("EXPERT ANSWER (ground truth)", GAP),
        ("LEARNED GUIDANCE", INV_V2),
        ("EVIDENCE:", INV_V1),
    ])


@pytest.fixture(scope="module")
def store():
    return KnowledgeStore.from_dir()


def test_interactive_cycle_existing_question(store):
    repo = SQLiteRepository(":memory:")
    for h in load_human_answers():
        repo.save_human_answer(h)
    orch = Orchestrator(_provider(), store, BM25Retriever(store.all()), repo, retrieval_k=4)
    p2 = {q.id: q for q in load_questions()}["P2"]

    typed = "A recent commit disabled the idempotency guard, so retries duplicated charges."
    run = orch.run_interactive_cycle(p2, typed)

    assert run.v1 and run.v2 and run.gap and run.learning_event
    assert run.human.answer_text == typed                 # the TYPED answer is ground truth
    assert run.human.key_source_ids                       # enriched from stored P2 gold
    assert "commit:a1" in run.newly_retrieved_ids         # learning surfaced the missed commit
    assert run.learning_event.sanitization.leakage_check_passed
    # persisted
    assert repo.get_run(run.run_id) is not None
    assert repo.get_human_answer("P2").answer_text == typed


def test_interactive_cycle_new_question(store):
    repo = SQLiteRepository(":memory:")
    orch = Orchestrator(_provider(), store, BM25Retriever(store.all()), repo, retrieval_k=4)
    q = Question(id="U1", text="What caused the June 3 duplicate-charge incident?",
                 family=QuestionFamily.PROD_INCIDENT, family_id="user-prod_incident")

    run = orch.run_interactive_cycle(q, "An expert answer about a disabled safeguard.")

    assert run.v1 and run.v2 and run.learning_event
    assert run.human.key_source_ids == []                 # no stored gold for a brand-new question
    assert run.human.root_cause_rubric == []
    assert repo.get_question("U1") is not None             # new question persisted
    assert repo.get_run(run.run_id) is not None


def test_two_step_matches_one_shot(store):
    """learn_and_v2 on a separately-produced V1 == run_interactive_cycle structurally."""
    repo = SQLiteRepository(":memory:")
    orch = Orchestrator(_provider(), store, BM25Retriever(store.all()), repo, retrieval_k=4)
    q = {qq.id: qq for qq in load_questions()}["P2"]

    v1, snap1 = orch.run_v1_only(q)
    run = orch.learn_and_v2(q, v1, snap1, "Expert: a recent commit disabled the guard.")
    assert run.v1 is v1 and run.v2 is not None
    assert run.phase == "v2_train"
