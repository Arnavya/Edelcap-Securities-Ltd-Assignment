"""In-memory store over the evidence corpus.

Loads all sources once and resolves stable ids in O(1) — used by the pipeline to
turn cited ``source_id``s back into full evidence for the reasoning prompt and the
dashboard.
"""

from __future__ import annotations

from pathlib import Path

from ..models import EvidenceItem, SourceType
from .loaders import load_evidence


class KnowledgeStore:
    def __init__(self, items: list[EvidenceItem]) -> None:
        self._items = list(items)
        self._by_id: dict[str, EvidenceItem] = {it.source_id: it for it in items}
        if len(self._by_id) != len(self._items):
            raise ValueError("duplicate source_id in evidence corpus")

    @classmethod
    def from_dir(cls, data_dir: Path | None = None) -> "KnowledgeStore":
        return cls(load_evidence(data_dir))

    def get(self, source_id: str) -> EvidenceItem | None:
        return self._by_id.get(source_id)

    def require(self, source_id: str) -> EvidenceItem:
        item = self._by_id.get(source_id)
        if item is None:
            raise KeyError(f"unknown source_id: {source_id}")
        return item

    def all(self) -> list[EvidenceItem]:
        return list(self._items)

    def by_source_type(self, source_type: SourceType) -> list[EvidenceItem]:
        return [it for it in self._items if it.source_type == source_type]

    def __len__(self) -> int:
        return len(self._items)
