"""Gap analysis — AI answer vs human ground truth."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .answer import AnswerVersion

Severity = Literal["low", "medium", "high"]


class GapAnalysis(BaseModel):
    """Where the AI answer fell short of the expert answer.

    Evidence diffs (``missed_evidence_ids`` / ``extra_evidence_ids``) are computed
    deterministically; the reasoning/root-cause gaps come from the gap agent.
    """

    question_id: str
    compared_version: AnswerVersion = AnswerVersion.V1
    reasoning_gaps: list[str] = Field(default_factory=list)
    missed_evidence_ids: list[str] = Field(default_factory=list)
    extra_evidence_ids: list[str] = Field(default_factory=list)
    missed_root_causes: list[str] = Field(default_factory=list)
    severity: Severity = "medium"
    narrative: str = ""
