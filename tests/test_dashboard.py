"""P8: dashboard data layer — read-only view-models over persisted artifacts."""

import pytest

from dashboard import data
from finflow.models import (
    Answer,
    AnswerVersion,
    EvaluationRun,
    GapAnalysis,
    GateResult,
    HumanAnswer,
    JudgeResult,
    LearningEvent,
    LearningPattern,
    PatternType,
    Question,
    QuestionFamily,
    QuestionScore,
    ReasoningStep,
    ReasoningTrace,
    RetrievalDiagnostics,
    RetrievalSnapshot,
    RetrievedItem,
    RunRecord,
    Sanitization,
    SourceType,
)
from finflow.persistence import SQLiteRepository


def _snap(version, ids, expansion_ids=()):
    items = [RetrievedItem(source_id=s, source_type=SourceType.COMMIT if s.startswith("commit") else SourceType.TICKET,
                           score=1.0, rank=i + 1, from_expansion=(s in expansion_ids))
             for i, s in enumerate(ids)]
    return RetrievalSnapshot(question_id="P2", version=version, query="q", items=items,
                             diagnostics=RetrievalDiagnostics(query="q", notes=["applied lp-1 (0.9)"]))


@pytest.fixture()
def repo():
    r = SQLiteRepository(":memory:")
    r.save_question(Question(id="P2", text="What caused the June 3 duplicate-charge incident?",
                             family=QuestionFamily.PROD_INCIDENT, family_id="fam-incident"))
    r.save_human_answer(HumanAnswer(question_id="P2", answer_text="retry storm + disabled guard",
                                    key_source_ids=["ticket:PAY-530", "commit:a1"]))
    event = LearningEvent(
        event_id="e1", source_question_id="P2", category=QuestionFamily.PROD_INCIDENT,
        patterns=[
            LearningPattern(id="lp-1", pattern_type=PatternType.EXPERT_HEURISTIC,
                            applies_to_family=QuestionFamily.PROD_INCIDENT, hint_text="check recent commits"),
            LearningPattern(id="lp-2", pattern_type=PatternType.MISSED_EVIDENCE,
                            applies_to_family=QuestionFamily.PROD_INCIDENT, hint_text="recent commit",
                            retrieval_signals=["refactor", "revert"]),
        ],
        sanitization=Sanitization(leakage_check_passed=True, max_ngram_overlap=0.0, redactions=1))
    run = RunRecord(
        run_id="P2-cycle-1", question_id="P2", phase="v2_train",
        v1=Answer(question_id="P2", version=AnswerVersion.V1, answer_text="timeouts caused retries",
                  cited_source_ids=["ticket:PAY-530", "slack:inc-jun3-charge"],
                  reasoning_trace=ReasoningTrace(steps=[ReasoningStep(claim="timeouts", cited_source_ids=["ticket:PAY-530"], confidence=0.7)])),
        v2=Answer(question_id="P2", version=AnswerVersion.V2, answer_text="a commit disabled the guard",
                  cited_source_ids=["ticket:PAY-530", "slack:inc-jun3-charge", "commit:a1"],
                  injected_pattern_ids=["lp-1", "lp-2"],
                  reasoning_trace=ReasoningTrace(steps=[ReasoningStep(claim="guard disabled", cited_source_ids=["commit:a1"], confidence=0.9)])),
        retrieval_v1=_snap("V1", ["ticket:PAY-530", "slack:inc-jun3-charge"]),
        retrieval_v2=_snap("V2", ["ticket:PAY-530", "slack:inc-jun3-charge", "commit:a1"], expansion_ids=["commit:a1"]),
        human=HumanAnswer(question_id="P2", answer_text="retry storm + disabled guard"),
        gap=GapAnalysis(question_id="P2", missed_evidence_ids=["commit:a1"], severity="high",
                        reasoning_gaps=["did not check commits"], missed_root_causes=["disabled guard"]),
        learning_event=event,
        newly_retrieved_ids=["commit:a1"], newly_cited_ids=["commit:a1"],
    )
    r.save_run(run)
    r.save_learning_event(event)
    r.save_judge_result("P2-cycle-1", JudgeResult(judge_event_id="j1", metric="answer_similarity", score=0.8,
                                                  judge_prompt_version="judge_similarity_v2", judge_model="groq:x"))
    ev = EvaluationRun(
        eval_id="eval-1", model="llama-3.3-70b-versatile",
        judge_prompt_versions={"similarity": "judge_similarity_v2", "root_cause": "judge_root_cause_v1"},
        scores=[
            QuestionScore(question_id="P2", phase="train", blended_v1=0.45, blended_v2=0.78,
                          root_cause_v1=0.12, root_cause_v2=0.5, evidence_utilization=0.5, improvement_rel=0.7),
            QuestionScore(question_id="H2", phase="heldout", is_held_out=True, blended_v1=0.45, blended_v2=0.78,
                          ablation_blended=0.65, root_cause_v1=0.5, root_cause_v2=0.75, evidence_utilization=0.17),
        ],
        gates=[GateResult(name="held_out_generalization", passed=True, central=True, value=0.33, threshold=0.10),
               GateResult(name="leakage_free_learning", passed=True, central=True, value=0.0, threshold=0.0)],
        verdict=True, central_claim_passed=True)
    r.save_evaluation_run(ev)
    return r


# --- read-only view-models ---------------------------------------------------

def test_question_feed(repo):
    feed = data.question_feed(repo)
    assert feed and feed[0]["id"] == "P2"
    assert feed[0]["has_v2"] is True


def test_evidence_comparison_flags_new_evidence(repo):
    run = data.latest_run(repo, "P2")
    rows = {r["source_id"]: r for r in data.evidence_comparison(run)}
    a1 = rows["commit:a1"]
    assert a1["newly_retrieved"] and a1["newly_cited"]
    assert a1["retrieved_v2"] and not a1["retrieved_v1"]
    pay = rows["ticket:PAY-530"]
    assert not pay["newly_retrieved"] and pay["cited_v1"] and pay["cited_v2"]


def test_evidence_utilization(repo):
    run = data.latest_run(repo, "P2")
    assert data.evidence_utilization(run) == 1.0  # a1 newly retrieved and referenced


def test_run_detail_includes_traces_and_judges(repo):
    run = data.latest_run(repo, "P2")
    d = data.run_detail(repo, run)
    assert d["v1"] and d["v2"] and d["expert"]
    assert d["retrieval_v2"]["items"]
    assert any(it["from_expansion"] for it in d["retrieval_v2"]["items"])
    assert d["judge_results"] and d["judge_results"][0]["metric"] == "answer_similarity"
    assert d["gap"]["severity"] == "high"


def test_learning_event_view_groups_and_leakage(repo):
    le = data.all_learning_events(repo)[0]
    assert "expert_heuristic" in le["patterns_by_type"]
    assert "missed_evidence" in le["patterns_by_type"]
    assert le["leakage"]["passed"] is True
    assert le["leakage"]["redactions"] == 1


def test_evaluation_summary_and_transfer(repo):
    ev = data.evaluation_summary(repo)
    assert ev["central_claim_passed"] is True
    gate_names = {g["name"] for g in ev["gates"]}
    assert "held_out_generalization" in gate_names

    full = repo.latest_evaluation_run()
    tm = data.transfer_metrics(full)
    assert len(tm) == 1 and tm[0]["question_id"] == "H2"
    assert tm[0]["held_out_delta"] == pytest.approx(0.33, abs=1e-6)
    assert tm[0]["ablation_delta"] == pytest.approx(0.13, abs=1e-6)


def test_metrics_chart_frame(repo):
    ev = repo.latest_evaluation_run()
    rows = data.metrics_chart_frame(ev)
    assert len(rows) == 4  # 2 questions x {V1,V2}
    assert {r["version"] for r in rows} == {"V1", "V2"}
