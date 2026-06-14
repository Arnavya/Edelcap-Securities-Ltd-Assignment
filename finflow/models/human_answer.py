"""Human expert answers — the ground truth."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RubricElement(BaseModel):
    """One required element of a question's canonical causal chain.

    Used by the root-cause judge to score coverage element-by-element.
    """

    id: str
    description: str


class HumanAnswer(BaseModel):
    """The expert's ground-truth answer plus the gold sets used for scoring."""

    question_id: str
    answer_text: str
    root_causes: list[str] = Field(default_factory=list)
    key_source_ids: list[str] = Field(default_factory=list)
    root_cause_rubric: list[RubricElement] = Field(default_factory=list)
    expert: str | None = None
    created_at: datetime | None = None
