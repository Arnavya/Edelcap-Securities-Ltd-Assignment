"""Evidence items — the citable units of the knowledge base."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    SLACK = "slack"
    TICKET = "ticket"
    WIKI = "wiki"
    COMMIT = "commit"


class EvidenceItem(BaseModel):
    """A single piece of evidence with a stable, human-readable id.

    ``source_id`` examples: ``ticket:LED-412``, ``slack:inc-jun3-charge``,
    ``wiki:ownership-matrix``, ``commit:a1``. The pipeline only ever cites by
    ``source_id`` so citations stay valid across runs.
    """

    source_id: str
    source_type: SourceType
    title: str
    body: str
    service: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    author: str | None = None
