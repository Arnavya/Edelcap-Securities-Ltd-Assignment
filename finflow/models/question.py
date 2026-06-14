"""Questions captured from the (simulated) Slack-style feed."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class QuestionFamily(str, Enum):
    RELEASE_DELAY = "release_delay"
    PROD_INCIDENT = "prod_incident"
    SERVICE_OWNERSHIP = "service_ownership"
    DESIGN_DECISION = "design_decision"
    MILESTONE_BLOCKAGE = "milestone_blockage"


class Question(BaseModel):
    """An organizational question.

    ``family_id`` groups a train question with its held-out twin (same reasoning
    pattern, different entities) so generalization can be measured.
    """

    id: str
    text: str
    family: QuestionFamily
    family_id: str | None = None
    is_held_out: bool = False
    requires_cross_source: bool = True
    asked_by: str | None = None
    channel: str | None = None
    timestamp: datetime | None = None
    tags: list[str] = Field(default_factory=list)
