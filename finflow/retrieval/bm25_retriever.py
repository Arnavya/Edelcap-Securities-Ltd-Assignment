"""Deterministic BM25 retrieval with per-source balancing and diagnostics.

Why per-source balancing: a naive global top-k lets one verbose source (e.g. wiki)
crowd out the others, which kills cross-source reasoning. We instead take the top
``k_per_source`` from each source and merge, guaranteeing every source has a fair
shot at the candidate set.

Routing bias (V2): preferred source types get a soft score multiplier — they are
favoured, never hard-filtered, so genuinely relevant evidence from other sources
still surfaces.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from ..models import (
    EvidenceItem,
    RetrievalDiagnostics,
    RetrievalSnapshot,
    RetrievedItem,
    SourceType,
)
from .expansion import ExpansionStrategy, NullExpansion
from .retriever import Retriever

_TOKEN_RE = re.compile(r"[a-z0-9]+")
DEFAULT_ROUTING_BOOST = 0.5
OFFSERVICE_PENALTY = 0.30  # soft down-rank for expansion-only off-service items (V2)

# Lightweight stopword list. Removing these keeps BM25 focused on content terms and
# prevents question boilerplate ("what/why/the/did") from spuriously matching docs —
# which is what otherwise lets V1 stumble onto evidence it shouldn't have found.
STOPWORDS = frozenset("""
a an the this that these those of in on at to for from by with without into over under
and or but not no nor so as is are was were be been being am do does did done doing
has have had having will would shall should can could may might must
i we you he she it they them us our your their its his her my me
what why how who whom which when where whose
about against between during before after above below up down out off than then once
here there all any both each few more most other some such only own same too very
it's its' s t re ve ll d m o
""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def _index_text(item: EvidenceItem) -> str:
    parts = [item.title, item.body, " ".join(item.tags)]
    if item.service:
        parts.append(item.service)
    return " ".join(parts)


class BM25Retriever(Retriever):
    def __init__(
        self,
        items: list[EvidenceItem],
        *,
        expansion: ExpansionStrategy | None = None,
        routing_boost: float = DEFAULT_ROUTING_BOOST,
    ) -> None:
        if not items:
            raise ValueError("BM25Retriever requires a non-empty corpus")
        self._items = list(items)
        self._tokens = [tokenize(_index_text(it)) for it in self._items]
        self._token_sets = [set(toks) for toks in self._tokens]
        self._bm25 = BM25Okapi(self._tokens)
        self._expansion = expansion or NullExpansion()
        self._routing_boost = routing_boost

    def search(
        self,
        query: str,
        *,
        k_per_source: int = 4,
        expansion_terms: list[str] | None = None,
        routing_sources: list[SourceType] | None = None,
        source_filter: list[SourceType] | None = None,
        service_scope: str | None = None,
        max_results: int | None = None,
        question_id: str | None = None,
        version: str = "V1",
    ) -> RetrievalSnapshot:
        base_terms = tokenize(query)

        # Compose expansion: explicit per-call terms + attached strategy.
        explicit = list(expansion_terms or [])
        strat = self._expansion.expand(query, base_terms)
        expansion_strings = explicit + strat
        exp_tokens = tokenize(" ".join(expansion_strings))

        base_set = set(base_terms)
        exp_set = set(exp_tokens)
        query_tokens = base_terms + exp_tokens

        routing = list(routing_sources or [])
        diagnostics = RetrievalDiagnostics(
            query=query,
            base_terms=base_terms,
            expansion_terms=expansion_strings,
            routing_sources=routing,
            routing_boost=self._routing_boost if routing else 0.0,
            k_per_source=k_per_source,
            max_results=max_results,
        )

        if not query_tokens:
            diagnostics.notes.append("empty query — no terms to score")
            return RetrievalSnapshot(
                question_id=question_id, version=version, query=query, items=[],
                diagnostics=diagnostics,
            )

        scores = self._bm25.get_scores(query_tokens)

        # Group scored candidates by source (respecting an optional hard filter).
        allowed = set(source_filter) if source_filter else None
        per_source: dict[SourceType, list[tuple[float, int]]] = {}
        candidate_counts: dict[str, int] = {}
        down_ranked = 0  # expansion-only off-service items soft-penalized by service_scope
        for idx, raw_score in enumerate(scores):
            item = self._items[idx]
            if allowed is not None and item.source_type not in allowed:
                continue
            score = float(raw_score)
            if score <= 0.0:
                continue
            # Minimal V2 cross-service guard: SOFT down-rank (not drop) expansion-ONLY
            # results whose service differs from the dominant V1 service. Base-matched
            # and service=None items are never penalized.
            if service_scope is not None:
                doc = self._token_sets[idx]
                expansion_only = (not (base_set & doc)) and bool(exp_set & doc)
                if expansion_only and item.service is not None and item.service != service_scope:
                    score *= OFFSERVICE_PENALTY
                    down_ranked += 1
            if routing and item.source_type in routing:
                score *= 1.0 + self._routing_boost
            per_source.setdefault(item.source_type, []).append((score, idx))
            candidate_counts[item.source_type.value] = candidate_counts.get(item.source_type.value, 0) + 1

        # Per-source balancing: top-k from each source, then merge.
        selected: list[tuple[float, int]] = []
        for stype, scored in per_source.items():
            scored.sort(key=lambda x: (-x[0], self._items[x[1]].source_id))
            selected.extend(scored[:k_per_source])

        # Final ranking across sources; stable tie-break by source_id.
        selected.sort(key=lambda x: (-x[0], self._items[x[1]].source_id))
        if max_results is not None:
            selected = selected[:max_results]

        items: list[RetrievedItem] = []
        per_source_counts: dict[str, int] = {}
        for rank, (score, idx) in enumerate(selected, start=1):
            item = self._items[idx]
            doc = self._token_sets[idx]
            matched_base = base_set & doc
            matched_exp = exp_set & doc
            matched = sorted(matched_base | matched_exp)
            from_expansion = (not matched_base) and bool(matched_exp)
            items.append(RetrievedItem(
                source_id=item.source_id,
                source_type=item.source_type,
                score=round(score, 4),
                rank=rank,
                matched_terms=matched,
                from_expansion=from_expansion,
            ))
            per_source_counts[item.source_type.value] = per_source_counts.get(item.source_type.value, 0) + 1

        diagnostics.candidate_counts = candidate_counts
        diagnostics.per_source_counts = per_source_counts
        if expansion_strings:
            n_exp = sum(1 for it in items if it.from_expansion)
            diagnostics.notes.append(f"{n_exp} item(s) surfaced via expansion")
        if routing:
            diagnostics.notes.append(
                f"routing bias x{1.0 + self._routing_boost:.2f} on "
                + ", ".join(s.value for s in routing)
            )
        if service_scope is not None:
            diagnostics.notes.append(
                f"v2 service-scoped to '{service_scope}'; down-ranked {down_ranked} "
                f"off-service expansion item(s) x{OFFSERVICE_PENALTY}"
            )

        return RetrievalSnapshot(
            question_id=question_id, version=version, query=query, items=items,
            diagnostics=diagnostics,
        )
