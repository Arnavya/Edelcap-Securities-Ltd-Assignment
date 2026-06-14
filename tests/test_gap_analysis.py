"""P5: gap analysis — deterministic evidence diff + LLM semantic gaps."""

import pytest

from finflow.agents import GapAnalysisAgent, evidence_diff, severity
from finflow.agents.investigation_agent import InvestigationAgent
from finflow.models import Answer, AnswerVersion, ReasoningStep, ReasoningTrace
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_human_answers, load_questions

from .helpers import RoutingProvider, ScriptedProvider

GAP_RESPONSE = {
    "reasoning_gaps": ["did not check recent commits for a removed safeguard"],
    "missed_root_causes": ["idempotency guard disabled (commit a1)", "fix via revert (a15)"],
    "narrative": "Stopped at the proximate cause (timeouts) without inspecting recent changes.",
}
GAP_EMPTY = {"reasoning_gaps": [], "missed_root_causes": [], "narrative": "Complete."}

INVESTIGATION_RESPONSE = {
    "reasoning_steps": [{"claim": "Double charges on Jun 3.", "cited_source_ids": ["slack:inc-jun3-charge"], "confidence": 0.8}],
    "candidate_root_causes": ["retries during timeouts"],
    "summary": "Joined incident thread and RCA ticket.",
    "answer_text": "Caused by payment retries during Risk timeouts.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge"],
}


@pytest.fixture(scope="module")
def store():
    return KnowledgeStore.from_dir()


@pytest.fixture(scope="module")
def p2():
    return {q.id: q for q in load_questions()}["P2"]


@pytest.fixture(scope="module")
def p2_human():
    return {h.question_id: h for h in load_human_answers()}["P2"]


# --- deterministic helpers ---------------------------------------------------

def test_evidence_diff():
    matched, missed, extra = evidence_diff(
        cited=["a", "b", "x"], gold=["a", "b", "c"]
    )
    assert matched == ["a", "b"]
    assert missed == ["c"]
    assert extra == ["x"]


def test_severity_levels():
    assert severity(missed=["a", "b", "c"], gold=["a", "b", "c", "d"], n_missed_root_causes=0) == "high"
    assert severity(missed=[], gold=["a", "b"], n_missed_root_causes=2) == "high"
    assert severity(missed=["a"], gold=["a", "b", "c", "d"], n_missed_root_causes=0) == "medium"
    assert severity(missed=[], gold=["a", "b"], n_missed_root_causes=0) == "low"


# --- agent -------------------------------------------------------------------

def _answer(cited):
    return Answer(
        question_id="P2", version=AnswerVersion.V1,
        answer_text="Caused by retries during Risk timeouts.",
        cited_source_ids=cited,
        reasoning_trace=ReasoningTrace(
            steps=[ReasoningStep(claim="retries", cited_source_ids=cited, confidence=0.8)],
            candidate_root_causes=["retry storm"],
        ),
    )


def test_gap_agent_deterministic_diff_and_llm_gaps(p2, p2_human):
    agent = GapAnalysisAgent(ScriptedProvider(GAP_RESPONSE))
    answer = _answer(["ticket:PAY-530", "slack:inc-jun3-charge"])
    gap = agent.analyze(p2, answer, p2_human)

    # deterministic evidence diff against P2 gold
    assert gap.missed_evidence_ids == ["commit:a1", "commit:a15", "commit:a3", "ticket:RISK-220"]
    assert gap.extra_evidence_ids == []
    assert gap.compared_version is AnswerVersion.V1
    # LLM semantic gaps
    assert gap.reasoning_gaps == GAP_RESPONSE["reasoning_gaps"]
    assert len(gap.missed_root_causes) == 2
    assert gap.severity == "high"  # 4/6 missed + 2 missed root causes


def test_gap_agent_complete_answer_is_low_severity(p2, p2_human):
    agent = GapAnalysisAgent(ScriptedProvider(GAP_EMPTY))
    answer = _answer(list(p2_human.key_source_ids))  # cite all gold
    gap = agent.analyze(p2, answer, p2_human)
    assert gap.missed_evidence_ids == []
    assert gap.severity == "low"


# --- orchestrator end-to-end (investigation + gap, persisted) ----------------

def test_orchestrator_persists_gap(store, p2):
    provider = RoutingProvider(rules=[
        ("EXPERT ANSWER (ground truth)", GAP_RESPONSE),   # gap_v1 prompt
        ("EVIDENCE:", INVESTIGATION_RESPONSE),            # investigation_v1 prompt
    ])
    repo = SQLiteRepository(":memory:")
    for h in load_human_answers():
        repo.save_human_answer(h)
    orch = Orchestrator(provider, store, BM25Retriever(store.all()), repo, retrieval_k=4)

    run = orch.run_v1(p2)
    gap = orch.add_gap_analysis(run)

    assert gap.missed_evidence_ids  # something was missed
    reloaded = repo.get_run(run.run_id)
    assert reloaded.gap is not None
    assert reloaded.gap.question_id == "P2"
    assert reloaded.gap.severity in {"low", "medium", "high"}
    assert reloaded.human is not None
