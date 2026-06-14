"""P4: end-to-end V1 investigation + persistence (offline via ScriptedProvider)."""

import pytest

from finflow.agents import InvestigationAgent
from finflow.agents.json_parsing import extract_json_object
from finflow.models import AnswerVersion
from finflow.orchestrator import Orchestrator
from finflow.persistence import SQLiteRepository
from finflow.retrieval import BM25Retriever, KnowledgeStore, load_human_answers, load_questions

from .helpers import ScriptedProvider

# A scripted V1 response for P2 that cites two genuinely-retrieved ids plus one
# hallucinated id (must be dropped) and an out-of-range confidence (must be clamped).
P2_RESPONSE = {
    "reasoning_steps": [
        {"claim": "Customers were double-charged on June 3.",
         "cited_source_ids": ["slack:inc-jun3-charge"], "confidence": 0.9},
        {"claim": "A fabricated step citing nothing real.",
         "cited_source_ids": ["commit:zzz-not-real"], "confidence": 1.7},
    ],
    "candidate_root_causes": ["retry storm during Risk timeouts"],
    "summary": "Joined the incident thread with the RCA ticket.",
    "answer_text": "Duplicate charges were caused by payment retries during Risk Engine timeouts.",
    "cited_source_ids": ["ticket:PAY-530", "slack:inc-jun3-charge", "commit:zzz-not-real"],
}


@pytest.fixture(scope="module")
def store():
    return KnowledgeStore.from_dir()


@pytest.fixture()
def orchestrator(store):
    provider = ScriptedProvider(P2_RESPONSE)
    repo = SQLiteRepository(":memory:")
    for h in load_human_answers():
        repo.save_human_answer(h)
    return Orchestrator(provider, store, BM25Retriever(store.all()), repo, retrieval_k=4)


@pytest.fixture()
def p2():
    return {q.id: q for q in load_questions()}["P2"]


# --- JSON parsing util -------------------------------------------------------

def test_extract_json_plain():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_json_fenced_and_wrapped():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json_object('Sure! Here:\n{"a": {"b": 2}}\nThanks') == {"a": {"b": 2}}


def test_extract_json_raises_on_garbage():
    with pytest.raises(ValueError):
        extract_json_object("no json here")


# --- Agent: structured output, validated citations, confidence ---------------

def test_agent_produces_structured_answer(store, p2):
    agent = InvestigationAgent(ScriptedProvider(P2_RESPONSE), BM25Retriever(store.all()), store)
    answer, snapshot = agent.investigate(p2, version=AnswerVersion.V1, k_per_source=4)

    assert answer.version is AnswerVersion.V1
    assert answer.answer_text
    assert answer.provider == "scripted"
    assert answer.prompt_versions == {"investigation": "investigation_v1"}
    assert answer.injected_pattern_ids == []  # V1


def test_citations_are_validated_against_retrieval(store, p2):
    agent = InvestigationAgent(ScriptedProvider(P2_RESPONSE), BM25Retriever(store.all()), store)
    answer, snapshot = agent.investigate(p2, k_per_source=4)

    retrieved = set(snapshot.source_ids)
    # hallucinated id dropped everywhere
    assert "commit:zzz-not-real" not in answer.cited_source_ids
    for step in answer.reasoning_trace.steps:
        assert "commit:zzz-not-real" not in step.cited_source_ids
        assert set(step.cited_source_ids) <= retrieved
    # genuine, retrieved citations preserved
    assert "ticket:PAY-530" in answer.cited_source_ids
    assert set(answer.cited_source_ids) <= retrieved


def test_confidence_is_clamped(store, p2):
    agent = InvestigationAgent(ScriptedProvider(P2_RESPONSE), BM25Retriever(store.all()), store)
    answer, _ = agent.investigate(p2, k_per_source=4)
    confs = [s.confidence for s in answer.reasoning_trace.steps]
    assert all(0.0 <= c <= 1.0 for c in confs)
    assert max(confs) == 1.0  # the 1.7 was clamped


# --- Orchestrator + persistence (first-class) --------------------------------

def test_run_v1_persists_self_contained_run(orchestrator, p2):
    run = orchestrator.run_v1(p2)
    repo = orchestrator.repo

    # run persisted and reloadable
    reloaded = repo.get_run(run.run_id)
    assert reloaded is not None
    assert reloaded.v1.question_id == "P2"
    assert reloaded.phase == "baseline_train"

    # retrieval linkage travels with the run
    assert reloaded.retrieval_v1 is not None
    assert reloaded.retrieval_v1.source_ids
    assert set(reloaded.v1.cited_source_ids) <= set(reloaded.retrieval_v1.source_ids)

    # human ground truth linked (seeded)
    assert reloaded.human is not None and reloaded.human.question_id == "P2"

    # flat tables populated for dashboard queries
    assert repo.get_question("P2") is not None
    answers = repo.get_answers("P2")
    assert any(a.version is AnswerVersion.V1 for a in answers)
    assert repo.latest_run("P2").run_id == run.run_id


def test_run_v1_is_repeatable_with_distinct_run_ids(orchestrator, p2):
    r1 = orchestrator.run_v1(p2)
    r2 = orchestrator.run_v1(p2)
    assert r1.run_id != r2.run_id
    assert len(orchestrator.repo.list_runs("P2")) == 2
