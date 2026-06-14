"""P7: hybrid evaluation, judges, deterministic metrics, four gates, persistence."""

import json

import pytest

from finflow.evaluation import blended, compute_overlap, relative_improvement
from finflow.evaluation.evaluator import Evaluator
from finflow.evaluation.judge import Judge
from finflow.llm.base import LLMProvider
from finflow.models import Answer, AnswerVersion
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_human_answers, load_questions

from .helpers import RoutingProvider

# --- scripted orchestrator responses (incident family) -----------------------

INVESTIGATION_V1 = {
    "reasoning_steps": [{"claim": "Double charges.", "cited_source_ids": ["slack:inc-jun3-charge"], "confidence": 0.7}],
    "candidate_root_causes": ["retries during timeouts"],
    "summary": "incident thread", "answer_text": "Caused by retries during Risk Engine timeouts.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge"],
}
INVESTIGATION_V2 = {
    "reasoning_steps": [{"claim": "A commit removed a safeguard.", "cited_source_ids": ["commit:a1"], "confidence": 0.9}],
    "candidate_root_causes": ["disabled safeguard"],
    "summary": "checked commits", "answer_text": "A recent commit removed a safeguard; retries then duplicated.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge", "commit:a1", "commit:a15"],
}
GAP = {"reasoning_gaps": ["did not check recent commits"], "missed_root_causes": ["disabled guard"], "narrative": "n"}
LEARNING = {"patterns": [
    {"pattern_type": "source_routing", "hint_text": "Prefer recent commit history for incidents.",
     "routing_sources": ["commit", "ticket", "slack"], "retrieval_signals": [], "trigger_conditions": "incident", "confidence": 0.85},
    {"pattern_type": "missed_evidence", "hint_text": "The originating change is often a recent commit.",
     "retrieval_signals": ["refactor", "revert", "disable", "remove", "change", "perf"], "trigger_conditions": "dupes", "confidence": 0.8},
    {"pattern_type": "expert_heuristic", "hint_text": "Inspect recent commits for a removed safeguard before blaming a dependency.",
     "trigger_conditions": "incident", "confidence": 0.9},
]}


def orch_provider():
    return RoutingProvider(rules=[
        ("GENERALIZABLE investigative lessons", LEARNING),
        ("EXPERT ANSWER (ground truth)", GAP),
        ("LEARNED GUIDANCE", INVESTIGATION_V2),
        ("EVIDENCE:", INVESTIGATION_V1),
    ])


class JudgeProvider(LLMProvider):
    """Scores high when the candidate is the V2 answer (mentions a removed safeguard)."""

    name = "judge"
    model = "judge-1"

    def generate(self, prompt, *, system=None, max_tokens=1024, temperature=0.0) -> str:
        high = "removed a safeguard" in prompt
        if "RUBRIC (required root-cause elements)" in prompt:
            score = 1.0 if high else 0.25
            verdict = "hit" if high else "miss"
            return json.dumps({"per_element": [{"id": "RC1", "verdict": verdict, "score": score}],
                               "score": score, "reasoning": "r"})
        return json.dumps({"score": 90 if high else 40, "reasoning": "r"})


@pytest.fixture(scope="module")
def store():
    return KnowledgeStore.from_dir()


@pytest.fixture(scope="module")
def questions():
    return {q.id: q for q in load_questions()}


# --- deterministic helpers ---------------------------------------------------

def test_compute_overlap():
    r = compute_overlap(cited=["a", "b", "x"], gold=["a", "b", "c", "d"])
    assert r.recall == 0.5
    assert r.precision == pytest.approx(2 / 3, abs=1e-3)
    assert r.missed_ids == ["c", "d"]


def test_blended_and_improvement():
    assert blended(0.8, 1.0) == 0.9
    assert relative_improvement(0.4, 0.8) == 1.0


# --- judges ------------------------------------------------------------------

def test_similarity_judge_parses_and_logs(store, questions):
    judge = Judge(JudgeProvider())
    human = {h.question_id: h for h in load_human_answers()}["P2"]
    ans = Answer(question_id="P2", version=AnswerVersion.V2,
                 answer_text="A recent commit removed a safeguard; retries then duplicated.")
    jr = judge.similarity(questions["P2"], ans, human)
    assert jr.metric == "answer_similarity"
    assert jr.score == 0.9  # 90/100
    assert jr.judge_prompt_version == "judge_similarity_v2"


def test_root_cause_judge_uses_rubric(store, questions):
    judge = Judge(JudgeProvider())
    human = {h.question_id: h for h in load_human_answers()}["P2"]
    low = Answer(question_id="P2", version=AnswerVersion.V1, answer_text="Caused by retries during Risk Engine timeouts.")
    jr = judge.root_cause(questions["P2"], low, human)
    assert jr.metric == "root_cause_coverage"
    assert jr.score == 0.25
    assert jr.structured_detail["per_element"]


# --- full evaluation + gates + persistence -----------------------------------

@pytest.fixture()
def evaluation(store, questions):
    repo = SQLiteRepository(":memory:")
    for h in load_human_answers():
        repo.save_human_answer(h)
    orch = Orchestrator(orch_provider(), store, BM25Retriever(store.all()), repo, retrieval_k=4)
    evaluator = Evaluator(orch, Judge(JudgeProvider()))
    ev = evaluator.evaluate([(questions["P2"], questions["H2"])])
    return ev, repo


def test_evaluation_produces_scores_and_gates(evaluation):
    ev, _ = evaluation
    assert len(ev.scores) == 2  # train + heldout
    gate_names = {g.name for g in ev.gates}
    assert gate_names == {
        "held_out_generalization", "ablation_attribution",
        "leakage_free_learning", "same_question_improvement",
    }


def test_central_claim_passes(evaluation):
    ev, _ = evaluation
    by_name = {g.name: g for g in ev.gates}
    assert by_name["held_out_generalization"].passed       # V2 >> V1 on held-out
    assert by_name["held_out_generalization"].central
    assert by_name["leakage_free_learning"].passed         # no verbatim
    assert by_name["leakage_free_learning"].value == 0.0
    assert ev.central_claim_passed is True
    assert ev.verdict is True  # all four gates


def test_evidence_utilization_recorded(evaluation):
    ev, _ = evaluation
    train = next(s for s in ev.scores if s.phase == "train")
    # P2 V2 newly retrieves the root-cause commit and the V2 answer cites it
    assert train.newly_retrieved_ids
    assert train.evidence_utilization > 0.0


def test_rubric_coverage_is_the_success_signal(evaluation):
    """Held-out lift is driven by similarity + rubric coverage (not source retrieval)."""
    ev, _ = evaluation
    held = next(s for s in ev.scores if s.phase == "heldout")
    assert held.root_cause_v2 > held.root_cause_v1
    assert held.blended_v2 > held.blended_v1


def test_evaluation_persisted_with_judge_logs(evaluation):
    ev, repo = evaluation
    reloaded = repo.get_evaluation_run(ev.eval_id)
    assert reloaded is not None
    assert reloaded.verdict == ev.verdict
    assert repo.latest_evaluation_run().eval_id == ev.eval_id
    # every judge call was logged
    logs = repo.list_judge_results()
    assert len(logs) >= 10  # train(v1,v2)x2 + heldout(v1,v2,ablation)x2
    assert {l.metric for l in logs} == {"answer_similarity", "root_cause_coverage"}
