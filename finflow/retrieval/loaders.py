"""Load the synthetic JSON corpus into typed models."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import EvidenceItem, HumanAnswer, Question, SourceType

SOURCE_FILES: dict[SourceType, str] = {
    SourceType.SLACK: "slack_threads.json",
    SourceType.TICKET: "tickets.json",
    SourceType.WIKI: "wiki.json",
    SourceType.COMMIT: "commits.json",
}


def default_data_dir() -> Path:
    """Repository ``data/`` directory (…./finflow/retrieval/loaders.py -> …./data)."""
    return Path(__file__).resolve().parents[2] / "data"


def _read_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_evidence(data_dir: Path | None = None) -> list[EvidenceItem]:
    data_dir = data_dir or default_data_dir()
    items: list[EvidenceItem] = []
    for fname in SOURCE_FILES.values():
        for raw in _read_json(data_dir / "sources" / fname):
            items.append(EvidenceItem.model_validate(raw))
    return items


def load_questions(data_dir: Path | None = None) -> list[Question]:
    data_dir = data_dir or default_data_dir()
    return [Question.model_validate(raw) for raw in _read_json(data_dir / "feed.json")]


def load_human_answers(data_dir: Path | None = None) -> list[HumanAnswer]:
    data_dir = data_dir or default_data_dir()
    return [HumanAnswer.model_validate(raw) for raw in _read_json(data_dir / "human_answers.json")]
