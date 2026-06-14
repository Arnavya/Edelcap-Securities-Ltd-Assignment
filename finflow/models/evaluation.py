"""Evaluation artifacts — judge results, deterministic metrics, run records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from .answer import Answer
from .gap import GapAnalysis
from .human_answer import HumanAnswer
from .learning import LearningEvent
from .retrieval import RetrievalSnapshot

JudgeMetric = Literal["answer_similarity", "root_cause_coverage"]
RunPhase = Literal[
    "baseline_train",
    "baseline_heldout",
    "v2_train",
    "post_learning_heldout",
    "ablation_heldout",
]


class JudgeResult(BaseModel):
    """One logged LLM-judge evaluation. Every judge call is persisted."""

    judge_event_id: str
    metric: JudgeMetric
    score: float
    reasoning: str = ""
    structured_detail: dict[str, Any] = Field(default_factory=dict)
    judge_prompt_version: str = ""
    judge_model: str = ""
    created_at: datetime | None = None


class EvidenceOverlapResult(BaseModel):
    """Deterministic set-overlap of cited vs gold evidence."""

    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0
    matched_ids: list[str] = Field(default_factory=list)
    missed_ids: list[str] = Field(default_factory=list)


class ImprovementResult(BaseModel):
    """Deterministic V1-vs-V2 comparison."""

    similarity_delta: float = 0.0
    root_cause_delta: float = 0.0
    evidence_f1_delta: float = 0.0
    blended_relative_improvement: float = 0.0
    improved: bool = False


class QuestionScore(BaseModel):
    """Scored V1 vs V2 (and ablation) for one question in an evaluation run."""

    question_id: str
    family_id: str | None = None
    is_held_out: bool = False
    phase: Literal["train", "heldout"] = "train"
    similarity_v1: float = 0.0
    similarity_v2: float = 0.0
    root_cause_v1: float = 0.0
    root_cause_v2: float = 0.0
    evidence_v1: float = 0.0
    evidence_v2: float = 0.0
    blended_v1: float = 0.0
    blended_v2: float = 0.0
    ablation_blended: float | None = None  # held-out only
    improvement_rel: float = 0.0
    # fraction of newly-retrieved (learning-surfaced) evidence actually used by V2
    evidence_utilization: float = 0.0
    newly_retrieved_ids: list[str] = Field(default_factory=list)
    newly_cited_ids: list[str] = Field(default_factory=list)


class GateResult(BaseModel):
    name: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    detail: str = ""
    central: bool = False  # part of the central claim?


class EvaluationRun(BaseModel):
    """Persisted artifact for a full evaluation pass."""

    eval_id: str
    model: str = ""
    judge_prompt_versions: dict[str, str] = Field(default_factory=dict)
    scores: list[QuestionScore] = Field(default_factory=list)
    gates: list[GateResult] = Field(default_factory=list)
    verdict: bool = False
    central_claim_passed: bool = False
    created_at: datetime | None = None


class RunRecord(BaseModel):
    """The full unit of work persisted per question/run."""

    run_id: str
    question_id: str
    phase: RunPhase | None = None
    v1: Answer | None = None
    v2: Answer | None = None
    retrieval_v1: RetrievalSnapshot | None = None
    retrieval_v2: RetrievalSnapshot | None = None
    human: HumanAnswer | None = None
    gap: GapAnalysis | None = None
    learning_event: LearningEvent | None = None
    judge_results: list[JudgeResult] = Field(default_factory=list)
    evidence_overlap: EvidenceOverlapResult | None = None
    improvement: ImprovementResult | None = None
    # V1->V2 deltas (populated when a V2 exists) — consumed by P7 anti-memorization gates.
    newly_retrieved_ids: list[str] = Field(default_factory=list)
    newly_cited_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
