"""P0: the data contracts import and validate."""

from finflow.config import load_settings
from finflow.models import (
    Answer,
    AnswerVersion,
    EvidenceItem,
    GapAnalysis,
    HumanAnswer,
    LearningEvent,
    LearningPattern,
    PatternType,
    Question,
    QuestionFamily,
    ReasoningStep,
    ReasoningTrace,
    RubricElement,
    SourceType,
)


def test_evidence_item_roundtrip():
    item = EvidenceItem(
        source_id="ticket:LED-412",
        source_type=SourceType.TICKET,
        title="Settlement idempotency bug",
        body="Double-posting under retry; blocks the v2.5 release.",
        service="Ledger",
        tags=["idempotency", "release-blocker"],
    )
    assert item.source_type is SourceType.TICKET
    assert EvidenceItem.model_validate(item.model_dump()) == item


def test_question_family_enum():
    q = Question(
        id="P1",
        text="Why did the May payment-settlement release slip two weeks?",
        family=QuestionFamily.RELEASE_DELAY,
        family_id="release-settlement",
    )
    assert q.requires_cross_source is True
    assert q.family.value == "release_delay"


def test_answer_carries_reasoning_trace():
    trace = ReasoningTrace(
        steps=[ReasoningStep(claim="LED-412 blocked the release", cited_source_ids=["ticket:LED-412"], confidence=0.8)],
        candidate_root_causes=["idempotency bug found in staging"],
        summary="Release held pending the fix.",
    )
    ans = Answer(
        question_id="P1",
        version=AnswerVersion.V1,
        answer_text="The release slipped due to a settlement idempotency bug.",
        cited_source_ids=["ticket:LED-412"],
        reasoning_trace=trace,
    )
    assert ans.version is AnswerVersion.V1
    assert ans.injected_pattern_ids == []
    assert ans.reasoning_trace.steps[0].confidence == 0.8


def test_human_answer_with_rubric():
    human = HumanAnswer(
        question_id="P1",
        answer_text="Held for LED-412 fix.",
        root_causes=["LED-412 idempotency bug"],
        key_source_ids=["ticket:LED-412", "slack:rel-may-settlement"],
        root_cause_rubric=[RubricElement(id="RC1", description="Identifies the blocking ticket")],
    )
    assert human.root_cause_rubric[0].id == "RC1"


def test_learning_event_has_no_answer_field():
    """The learning schema must not expose any verbatim-answer field."""
    forbidden = {"answer_text", "expert_answer", "human_answer", "answer"}
    assert forbidden.isdisjoint(LearningEvent.model_fields)
    assert forbidden.isdisjoint(LearningPattern.model_fields)


def test_learning_pattern_is_generalized():
    pat = LearningPattern(
        id="lp-1",
        pattern_type=PatternType.EXPERT_HEURISTIC,
        applies_to_family=QuestionFamily.PROD_INCIDENT,
        hint_text="For incident RCA, check recent commits for disabled safeguards.",
        trigger_conditions="incident during/after a deploy",
        confidence=0.7,
    )
    assert pat.pattern_type is PatternType.EXPERT_HEURISTIC


def test_gap_analysis_defaults():
    gap = GapAnalysis(question_id="P1")
    assert gap.severity == "medium"
    assert gap.missed_evidence_ids == []


def test_settings_mock_offline(monkeypatch):
    monkeypatch.setenv("FINFLOW_PROVIDER", "mock")
    s = load_settings(dotenv=False)
    assert s.is_mock is True
    assert s.model  # has a default model
