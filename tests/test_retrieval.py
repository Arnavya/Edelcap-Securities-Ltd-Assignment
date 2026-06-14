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

# --- minimal V2 service-scope filter (cross-incident contamination guard) -----

# Expansion terms surface: a1/a15 (Payment), a4 (Notification, "refactor"),
# adr-004 (Ledger, "idempotency"), q3-roadmap (service=None, "roadmap").
SCOPE_EXPANSION = ["idempotency", "disable", "perf", "refactor", "revert", "roadmap"]


from finflow.retrieval.bm25_retriever import OFFSERVICE_PENALTY


def _scores(snap):
    return {i.source_id: i.score for i in snap.items}


def test_service_scope_downranks_offservice_expansion(retriever):
    """SOFT down-rank (not drop): off-service expansion items are penalized, in-scope unchanged."""
    base = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, k_per_source=20))
    scoped = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, service_scope="Payment", k_per_source=20))
    # off-service expansion-only item is present but down-ranked, NOT dropped
    assert "commit:a4" in scoped and scoped["commit:a4"] < base["commit:a4"]
    assert scoped["commit:a4"] == pytest.approx(base["commit:a4"] * OFFSERVICE_PENALTY, abs=1e-3)
    # in-scope item unchanged
    assert scoped["commit:a1"] == base["commit:a1"]
    # service=None doc unchanged/kept
    assert "wiki:q3-roadmap" in scoped
    assert any("down-ranked" in n for n in retriever.search(
        P2_QUERY, expansion_terms=SCOPE_EXPANSION, service_scope="Payment", k_per_source=20).diagnostics.notes)


def test_service_scope_inverse(retriever):
    base = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, k_per_source=20))
    scoped = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, service_scope="Notification", k_per_source=20))
    assert scoped["commit:a1"] < base["commit:a1"]      # Payment off-service -> down-ranked
    assert scoped["commit:a4"] == base["commit:a4"]      # Notification in-scope -> unchanged


def test_service_scope_none_is_noop(retriever):
    a = retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, k_per_source=20)
    b = retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, service_scope=None, k_per_source=20)
    assert [(i.source_id, i.score) for i in a.items] == [(i.source_id, i.score) for i in b.items]


def test_service_scope_does_not_penalize_base_matches(retriever):
    """An off-service item that matches the QUESTION's own terms (base-matched) is NOT penalized."""
    base = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, k_per_source=20))
    scoped = _scores(retriever.search(P2_QUERY, expansion_terms=SCOPE_EXPANSION, service_scope="Payment", k_per_source=20))
    # inc-jun9-notif (Notification, off-service) is base-matched via "duplicate"/"incident" -> unchanged
    assert scoped["slack:inc-jun9-notif"] == base["slack:inc-jun9-notif"]


def test_snapshot_roundtrip(retriever, tmp_path):
    snap = retriever.search(P2_QUERY, question_id="P2", version="V2", expansion_terms=P2_EXPANSION)
    path = save_snapshot(snap, tmp_path)
    assert path.exists()
    reloaded = load_snapshot(path)
    assert reloaded.source_ids == snap.source_ids
    assert reloaded.diagnostics.expansion_terms == snap.diagnostics.expansion_terms
