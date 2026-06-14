"""The Retriever interface — the single seam the InvestigationAgent depends on.

A future ``SemanticRetriever`` (embeddings) implements this same contract and drops
in with no agent change. ``search`` returns a fully-diagnosed, persistable
``RetrievalSnapshot``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RetrievalSnapshot, SourceType


class Retriever(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        *,
        k_per_source: int = 4,
        expansion_terms: list[str] | None = None,
        routing_sources: list[SourceType] | None = None,
        source_filter: list[SourceType] | None = None,
        max_results: int | None = None,
        question_id: str | None = None,
        version: str = "V1",
    ) -> RetrievalSnapshot:
        """Return ranked evidence with diagnostics.

        ``expansion_terms`` / ``routing_sources`` are the learned-pattern hooks used
        in V2: expansion terms widen the query; routing sources softly *bias*
        (never hard-filter) ranking toward preferred source types. ``source_filter``
        is an optional hard restriction (mainly for testing).
        """
        raise NotImplementedError
