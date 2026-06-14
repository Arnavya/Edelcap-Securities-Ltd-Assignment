"""Retrieval data contracts — results, diagnostics, and persisted snapshots.

A ``RetrievalSnapshot`` is the full, replayable record of one retrieval: what was
returned, the per-item scores/matched-terms, and the diagnostics explaining *why*
(base terms, expansion terms, routing bias, per-source balancing). Persisting it
lets the dashboard show the V1 vs V2 retrieval difference and lets P6/P7 reason
about evidence coverage without re-running retrieval.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .evidence import SourceType


class RetrievedItem(BaseModel):
    source_id: str
    source_type: SourceType
    score: float
    rank: int
    matched_terms: list[str] = Field(default_factory=list)
    from_expansion: bool = False  # surfaced only because of expansion terms


class RetrievalDiagnostics(BaseModel):
    query: str
    base_terms: list[str] = Field(default_factory=list)
    expansion_terms: list[str] = Field(default_factory=list)
    routing_sources: list[SourceType] = Field(default_factory=list)
    routing_boost: float = 0.0
    k_per_source: int = 4
    max_results: int | None = None
    candidate_counts: dict[str, int] = Field(default_factory=dict)  # score>0 per source
    per_source_counts: dict[str, int] = Field(default_factory=dict)  # selected per source
    notes: list[str] = Field(default_factory=list)


class RetrievalSnapshot(BaseModel):
    question_id: str | None = None
    version: str = "V1"
    query: str = ""
    items: list[RetrievedItem] = Field(default_factory=list)
    diagnostics: RetrievalDiagnostics
    created_at: datetime | None = None

    @property
    def source_ids(self) -> list[str]:
        return [it.source_id for it in self.items]
