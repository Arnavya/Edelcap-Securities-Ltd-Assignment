"""P6: learning loop — sanitization, memory, V2, and H2 transfer."""

import pytest

from finflow.agents import LearningEventGenerator
from finflow.evaluation import contains_verbatim, overlap_fraction, sanitize_patterns
from finflow.memory import LearningMemory
from finflow.memory.learning_memory import RELEVANCE_THRESHOLD, relevance_score
from finflow.models import (
    LearningEvent,
    LearningPattern,
    PatternType,
    QuestionFamily,
    SourceType,
)
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_human_answers, load_questions

from .helpers import RoutingProvider

# --- shared scripted responses for an end-to-end incident cycle --------------

INVESTIGATION_V1 = {
    "reasoning_steps": [{"claim": "Double charges occurred.", "cited_source_ids": ["slack:inc-jun3-charge"], "confidence": 0.7}],
    "candidate_root_causes": ["retries during timeouts"],
    "summary": "Looked at the incident thread and RCA.",
    "answer_text": "Caused by retries during Risk Engine timeouts.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge"],
}
INVESTIGATION_V2 = {
    "reasoning_steps": [
        {"claim": "A recent commit disabled a safeguard.", "cited_source_ids": ["commit:a1"], "confidence": 0.9},
    ],
    "candidate_root_causes": ["disabled safeguard + retry storm"],
    "summary": "Checked recent commits for a removed safeguard.",
    "answer_text": "A recent commit removed a safeguard; retries then duplicated.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge", "commit:a1", "commit:a15"],
}
GAP = {
    "reasoning_gaps": ["did not check recent commits for a removed safeguard"],
    "missed_root_causes": ["a recent commit disabled the guard", "the fix reverted it"],
    "narrative": "Stopped at the proximate cause.",
}
# Note the deliberately-leaking last pattern (copies a chunk of the P2 expert answer).
LEARNING = {
    "patterns": [
        {"pattern_type": "source_routing", "hint_text": "Prefer the affected service's recent commit history when investigating an incident.",
         "routing_sources": ["commit", "ticket", "slack"], "retrieval_signals": [], "trigger_conditions": "production incident", "confidence": 0.85},
        {"pattern_type": "missed_evidence", "hint_text": "The originating change is often a recent code commit.",
         "routing_sources": [], "retrieval_signals": ["refactor", "revert", "disable", "remove", "change", "perf"], "trigger_conditions": "unexpected duplicate behavior", "confidence": 0.8},
        {"pattern_type": "expert_heuristic", "hint_text": "For incident root-cause analysis, inspect recent commits to the affected service for a removed or disabled safeguard before blaming an upstream dependency.",
         "routing_sources": [], "retrieval_signals": [], "trigger_conditions": "incident", "confidence": 0.9},
        {"pattern_type": "reasoning_gap", "hint_text": "Do not stop at the first visible symptom; verify recent changes.",
         "routing_sources": [], "retrieval_signals": [], "trigger_conditions": "any", "confidence": 0.7},
        {"pattern_type": "expert_heuristic", "hint_text": "hitting a settlement path whose idempotency guard had recently been disabled for performance",
         "routing_sources": [], "retrieval_signals": [], "trigger_conditions": "leak", "confidence": 0.5},
    ]
}


def incident_provider():
    return RoutingProvider(rules=[
        ("GENERALIZABLE investigative lessons", LEARNING),
        ("EXPERT ANSWER (ground truth)", GAP),
        ("LEARNED GUIDANCE", INVESTIGATION_V2),   # V2 investigation prompt has guidance
        ("EVIDENCE:", INVESTIGATION_V1),          # V1 investigation prompt
    ])


@pytest.fixture(scope="module")
def store():
    return KnowledgeStore.from_dir()


@pytest.fixture(scope="module")
def questions():
    return {q.id: q for q in load_questions()}


def make_orch(store):
    repo = SQLiteRepository(":memory:")
    for h in load_human_answers():
        repo.save_human_answer(h)
    return Orchestrator(incident_provider(), store, BM25Retriever(store.all()), repo, retrieval_k=4)


# --- leakage primitives ------------------------------------------------------

def test_overlap_and_verbatim():
    ref = "the idempotency guard had recently been disabled for performance"
    assert contains_verbatim("had recently been disabled for performance", ref)
    assert not contains_verbatim("inspect recent commits for removed safeguards", ref)
    assert overlap_fraction("xx yy zz qq ww", ref) == 0.0


def test_sanitize_drops_leaking_pattern():
    ref = "the idempotency guard had recently been disabled for performance reasons"
    clean = LearningPattern(id="p1", pattern_type=PatternType.EXPERT_HEURISTIC,
                            applies_to_family=QuestionFamily.PROD_INCIDENT,
                            hint_text="check recent commits for removed safeguards")
    leak = LearningPattern(id="p2", pattern_type=PatternType.EXPERT_HEURISTIC,
                           applies_to_family=QuestionFamily.PROD_INCIDENT,
                           hint_text="the idempotency guard had recently been disabled for performance")
    kept, dropped, max_overlap = sanitize_patterns([clean, leak], ref)
    assert [p.id for p in kept] == ["p1"]
    assert dropped == 1
    assert max_overlap > 0.0


# --- generator ---------------------------------------------------------------

def test_generator_produces_sanitized_answer_free_event(store, questions):
    gen = LearningEventGenerator(incident_provider(), store)
    p2 = questions["P2"]
    human = {h.question_id: h for h in load_human_answers()}["P2"]
    from finflow.models import Answer, AnswerVersion, GapAnalysis, ReasoningTrace
    v1 = Answer(question_id="P2", version=AnswerVersion.V1, answer_text="x",
                reasoning_trace=ReasoningTrace(candidate_root_causes=["retries"]))
    gap = GapAnalysis(question_id="P2", missed_evidence_ids=["commit:a1", "commit:a15"],
                      reasoning_gaps=["did not check commits"], missed_root_causes=["disabled guard"])

    event = gen.generate(p2, v1, gap, human)

    assert event.sanitization.leakage_check_passed is True
    assert event.sanitization.redactions == 1            # the leaking pattern was dropped
    assert len(event.patterns) == 4                       # 5 produced, 1 dropped
    # answer-free: no pattern field shares an n-gram with the expert answer
    for p in event.patterns:
        assert not contains_verbatim(p.hint_text, human.answer_text)
        assert not contains_verbatim(p.trigger_conditions, human.answer_text)


# --- memory aggregation ------------------------------------------------------

def test_memory_aggregates_context(store, questions):
    repo = SQLiteRepository(":memory:")
    mem = LearningMemory(repo)
    event = LearningEvent(
        event_id="e1", source_question_id="P2", family_id="fam-incident",
        category=QuestionFamily.PROD_INCIDENT, patterns=[
            LearningPattern(id="lp-1", pattern_type=PatternType.SOURCE_ROUTING,
                            applies_to_family=QuestionFamily.PROD_INCIDENT,
                            routing_sources=[SourceType.COMMIT], hint_text="prefer commits", confidence=0.9),
            LearningPattern(id="lp-2", pattern_type=PatternType.MISSED_EVIDENCE,
                            applies_to_family=QuestionFamily.PROD_INCIDENT,
                            retrieval_signals=["refactor", "revert"], hint_text="recent commit", confidence=0.8),
            LearningPattern(id="lp-3", pattern_type=PatternType.EXPERT_HEURISTIC,
                            applies_to_family=QuestionFamily.PROD_INCIDENT,
                            hint_text="inspect recent commits", confidence=0.85),
        ])
    mem.store(event)

    ctx = mem.context_for(questions["P2"])
    assert SourceType.COMMIT in ctx.routing_sources
    assert "refactor" in ctx.expansion_terms
    assert "inspect recent commits" in ctx.guidance_text
    assert ctx.pattern_ids and not ctx.is_empty

    # held-out twin excludes its own (none here) but still gets P2's family patterns
    ctx_h2 = mem.context_for(questions["H2"], exclude_question_ids={"H2"})
    assert not ctx_h2.is_empty


# --- P2 same-question learning cycle: improved retrieval + citations ----------

def test_p2_cycle_improves_retrieval_and_reasoning(store, questions):
    orch = make_orch(store)
    run = orch.run_learning_cycle(questions["P2"])

    assert run.v1 is not None and run.v2 is not None
    assert run.learning_event is not None
    assert run.v2.injected_pattern_ids  # learned patterns were applied
    # V1 missed the root-cause commit; V2 newly retrieves it
    assert "commit:a1" not in run.retrieval_v1.source_ids
    assert "commit:a1" in run.retrieval_v2.source_ids
    assert "commit:a1" in run.newly_retrieved_ids
    # reasoning improved: V2 newly cites the commit (validated against its retrieval)
    assert "commit:a1" in run.newly_cited_ids


# --- H2 transfer: P2's heuristic generalizes to the held-out twin ------------

def test_h2_transfer_from_p2(store, questions):
    orch = make_orch(store)
    orch.run_learning_cycle(questions["P2"])      # learn from the train twin
    run = orch.run_heldout(questions["H2"])        # held-out twin gets NO feedback

    # H2 never created its own learning event
    assert run.learning_event is None
    # it nonetheless applied the family's learned patterns (from P2)
    assert run.v2.injected_pattern_ids
    # the transferred "check recent commits" heuristic surfaces a4 that V1 missed
    assert "commit:a4" not in run.retrieval_v1.source_ids
    assert "commit:a4" in run.retrieval_v2.source_ids
    assert "commit:a4" in run.newly_retrieved_ids


def test_relevance_score_filters_service_specific(questions):
    p_general = LearningPattern(id="g", pattern_type=PatternType.EXPERT_HEURISTIC,
                               applies_to_family=QuestionFamily.PROD_INCIDENT, hint_text="x")
    p_payment = LearningPattern(id="s", pattern_type=PatternType.SOURCE_ROUTING,
                                applies_to_family=QuestionFamily.PROD_INCIDENT,
                                applies_to_services=["Payment"], hint_text="payment-specific routing")
    # general lesson is relevant to both incident questions
    assert relevance_score(p_general, questions["P2"]) >= RELEVANCE_THRESHOLD
    assert relevance_score(p_general, questions["H2"]) >= RELEVANCE_THRESHOLD
    # payment-specific lesson: relevant to P2 (payment) but NOT to H2 (notification)
    assert relevance_score(p_payment, questions["P2"]) >= RELEVANCE_THRESHOLD
    assert relevance_score(p_payment, questions["H2"]) < RELEVANCE_THRESHOLD


def test_memory_rejects_irrelevant_patterns_with_diagnostics(store, questions):
    repo = SQLiteRepository(":memory:")
    mem = LearningMemory(repo)
    mem.store(LearningEvent(
        event_id="e1", source_question_id="P2", family_id="fam-incident",
        category=QuestionFamily.PROD_INCIDENT, patterns=[
            LearningPattern(id="gen", pattern_type=PatternType.EXPERT_HEURISTIC,
                            applies_to_family=QuestionFamily.PROD_INCIDENT,
                            hint_text="inspect recent commits for removed safeguards", confidence=0.9),
            LearningPattern(id="svc", pattern_type=PatternType.SOURCE_ROUTING,
                            applies_to_family=QuestionFamily.PROD_INCIDENT, hint_text="payment routing",
                            applies_to_services=["Payment"], routing_sources=[SourceType.COMMIT], confidence=0.8),
        ]))
    ctx = mem.context_for(questions["H2"], exclude_question_ids={"H2"})
    applied = {a["pattern_id"] for a in ctx.applied_patterns}
    rejected = {r["pattern_id"] for r in ctx.rejected_patterns}
    assert "gen" in applied and "svc" in rejected
    assert "inspect recent commits for removed safeguards" in ctx.reasoning_heuristics
    assert any("rejected svc" in n for n in ctx.diagnostic_notes())


def test_h2_learning_event_has_no_verbatim_leak(store, questions):
    """CI gate: the transferred event must be verbatim-free vs the P2 expert answer."""
    orch = make_orch(store)
    cycle = orch.run_learning_cycle(questions["P2"])
    human = {h.question_id: h for h in load_human_answers()}["P2"]
    for p in cycle.learning_event.patterns:
        assert not contains_verbatim(p.hint_text, human.answer_text)
        assert not contains_verbatim(p.trigger_conditions, human.answer_text)
