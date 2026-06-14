"""The reasoning trace produced by the investigation agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReasoningStep(BaseModel):
    """One step of reasoning, citing the evidence that supports its claim."""

    claim: str
    cited_source_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.5


class ReasoningTrace(BaseModel):
    """An ordered, evidence-linked explanation of how an answer was reached."""

    steps: list[ReasoningStep] = Field(default_factory=list)
    candidate_root_causes: list[str] = Field(default_factory=list)
    summary: str = ""
    applied_heuristic_ids: list[str] = Field(default_factory=list)
