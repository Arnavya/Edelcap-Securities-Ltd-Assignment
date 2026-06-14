"""Learning events — generalizable patterns distilled from a gap.

Critically, **no field here may hold a verbatim expert (or AI) answer**. The
learning store contains only generalized, reusable guidance. A deterministic
leakage gate (see ``finflow.evaluation.leakage``) enforces this before persist.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .evidence import SourceType
from .question import QuestionFamily

SCHEMA_VERSION = "le-1.0"


class PatternType(str, Enum):
    REASONING_GAP = "reasoning_gap"
    MISSED_EVIDENCE = "missed_evidence"
    SOURCE_ROUTING = "source_routing"
    EXPERT_HEURISTIC = "expert_heuristic"


class LearningPattern(BaseModel):
    """A single reusable lesson. ``hint_text`` is generalized — never the answer."""

    id: str
    pattern_type: PatternType
    applies_to_family: QuestionFamily
    applies_to_services: list[str] = Field(default_factory=list)
    hint_text: str
    routing_sources: list[SourceType] = Field(default_factory=list)
    retrieval_signals: list[str] = Field(default_factory=list)
    trigger_conditions: str = ""
    confidence: float = 0.5


class MetricSnapshot(BaseModel):
    """V1-vs-human scores captured when the event was created."""

    similarity_v1: float | None = None
    root_cause_coverage_v1: float | None = None
    evidence_coverage_v1: float | None = None
    judge_event_ids: list[str] = Field(default_factory=list)


class Sanitization(BaseModel):
    """Proof that the anti-leakage gate ran and passed."""

    leakage_check_passed: bool = False
    max_ngram_overlap: float = 0.0
    redactions: int = 0


class LearningEvent(BaseModel):
    """Patterns learned from one (investigation, expert-feedback) pair."""

    event_id: str
    schema_version: str = SCHEMA_VERSION
    source_question_id: str
    family_id: str | None = None
    category: QuestionFamily | None = None
    question_fingerprint: str | None = None
    provider_model: str = ""
    prompt_version: str = ""
    patterns: list[LearningPattern] = Field(default_factory=list)
    metric_snapshot: MetricSnapshot = Field(default_factory=MetricSnapshot)
    judge_reasoning: str = ""
    sanitization: Sanitization = Field(default_factory=Sanitization)
    created_at: datetime | None = None
