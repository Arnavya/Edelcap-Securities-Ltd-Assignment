"""AI-produced answers (V1 and V2)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .reasoning import ReasoningTrace


class AnswerVersion(str, Enum):
    V1 = "V1"
    V2 = "V2"


class Answer(BaseModel):
    """An AI answer with its reasoning trace and provenance.

    ``injected_pattern_ids`` is empty for V1; for V2 it records which learned
    patterns were applied, so the learning effect is auditable.
    """

    question_id: str
    version: AnswerVersion
    answer_text: str
    cited_source_ids: list[str] = Field(default_factory=list)
    reasoning_trace: ReasoningTrace = Field(default_factory=ReasoningTrace)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    provider: str = ""
    model: str = ""
    injected_pattern_ids: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
