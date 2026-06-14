"""P3: retrieval — loading, BM25, per-source balancing, expansion, routing, snapshots."""

import pytest

from finflow.models import SourceType
from finflow.retrieval import (
    BM25Retriever,
    KnowledgeStore,
    StaticExpansion,
    load_snapshot,
    save_snapshot,
)

P2_QUERY = "What caused the June 3 duplicate-charge incident?"
P2_EXPANSION = ["idempotency", "guard", "disable", "revert"]


@pytest.fixture(scope="module")
def store() -> KnowledgeStore:
    return KnowledgeStore.from_dir()


@pytest.fixture(scope="module")
def retriever(store) -> BM25Retriever:
    return BM25Retriever(store.all())


# --- KnowledgeStore ----------------------------------------------------------

def test_store_loads_full_corpus(store):
    assert len(store) == 54
    assert store.require("commit:a1").source_type is SourceType.COMMIT
    assert store.get("does-not-exist") is None
    assert len(store.by_source_type(SourceType.WIKI)) == 8


# --- Basic search + diagnostics ----------------------------------------------

def test_search_returns_ranked_results_with_diagnostics(retriever):
    snap = retriever.search(P2_QUERY, question_id="P2", version="V1")
    assert snap.items, "expected some results"
    ranks = [it.rank for it in snap.items]
    assert ranks == sorted(ranks) == list(range(1, len(ranks) + 1))
    scores = [it.score for it in snap.items]
    assert scores == sorted(scores, reverse=True)
    assert snap.diagnostics.base_terms  # populated
    assert snap.diagnostics.candidate_counts


def test_search_is_deterministic(retriever):
    a = retriever.search(P2_QUERY)
    b = retriever.search(P2_QUERY)
    assert [i.model_dump() for i in a.items] == [i.model_dump() for i in b.items]


def test_cross_source_results(retriever):
    snap = retriever.search(P2_QUERY)
    kinds = {it.source_type for it in snap.items}
    assert len(kinds) >= 2, "P2 should retrieve multiple source types"


# --- Per-source balancing ----------------------------------------------------

def test_per_source_balancing_caps_each_source(retriever):
    snap = retriever.search("settlement idempotency ledger payment", k_per_source=2)
    for count in snap.diagnostics.per_source_counts.values():
        assert count <= 2


def test_max_results_cap(retriever):
    snap = retriever.search("settlement idempotency ledger payment", max_results=3)
    assert len(snap.items) == 3


# --- Expansion: the V1->V2 headline (a1 is missed by V1, found via expansion) -

def test_v1_misses_root_cause_commit(retriever):
    snap = retriever.search(P2_QUERY, version="V1")
    assert "commit:a1" not in snap.source_ids  # lexical gap — the whole point


def test_regression_p2_v1_misses_mechanism_commits(retriever):
    """Regression: V1 must not surface the idempotency commits (a1 disable, a15 revert).

    Guards the PAY-540 wording fix — the disabled-guard mechanism (rubric RC2) must
    only be reachable via V2 expansion, not handed to V1 by retrieval.
    """
    snap = retriever.search(P2_QUERY, version="V1")
    assert "commit:a1" not in snap.source_ids
    assert "commit:a15" not in snap.source_ids


def test_expansion_surfaces_root_cause_commit(retriever):
    snap = retriever.search(
        P2_QUERY,
        expansion_terms=P2_EXPANSION,
        routing_sources=[SourceType.COMMIT],
        version="V2",
    )
    assert "commit:a1" in snap.source_ids
    a1 = next(it for it in snap.items if it.source_id == "commit:a1")
    assert a1.from_expansion is True
    assert {"idempotency", "disable"} & set(a1.matched_terms)


def test_pluggable_expansion_strategy(store):
    r = BM25Retriever(store.all(), expansion=StaticExpansion(P2_EXPANSION))
    snap = r.search(P2_QUERY, routing_sources=[SourceType.COMMIT])
    assert "commit:a1" in snap.source_ids  # strategy contributed the terms
    assert snap.diagnostics.expansion_terms  # recorded for diagnostics


# --- Routing bias (soft, not a filter) ---------------------------------------

def test_routing_bias_raises_preferred_scores(store):
    r = BM25Retriever(store.all(), routing_boost=0.5)
    plain = r.search(P2_QUERY, expansion_terms=P2_EXPANSION)
    routed = r.search(P2_QUERY, expansion_terms=P2_EXPANSION, routing_sources=[SourceType.COMMIT])
    s_plain = next(i.score for i in plain.items if i.source_id == "commit:a1")
    s_routed = next(i.score for i in routed.items if i.source_id == "commit:a1")
    assert s_routed > s_plain
    assert routed.diagnostics.routing_boost == 0.5


def test_routing_does_not_hard_filter(retriever):
    """Even with commit routing, other sources still appear (bias, not filter)."""
    snap = retriever.search(P2_QUERY, expansion_terms=P2_EXPANSION, routing_sources=[SourceType.COMMIT])
    assert {it.source_type for it in snap.items} != {SourceType.COMMIT}


def test_source_filter_is_a_hard_restriction(retriever):
    snap = retriever.search(P2_QUERY, source_filter=[SourceType.TICKET])
    assert snap.items
    assert all(it.source_type is SourceType.TICKET for it in snap.items)


# --- Persisted snapshots -----------------------------------------------------

def test_snapshot_roundtrip(retriever, tmp_path):
    snap = retriever.search(P2_QUERY, question_id="P2", version="V2", expansion_terms=P2_EXPANSION)
    path = save_snapshot(snap, tmp_path)
    assert path.exists()
    reloaded = load_snapshot(path)
    assert reloaded.source_ids == snap.source_ids
    assert reloaded.diagnostics.expansion_terms == snap.diagnostics.expansion_terms
