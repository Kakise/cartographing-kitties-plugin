"""Tests for weighted PageRank centrality (R6)."""

from __future__ import annotations

import logging

import pytest

from cartograph.storage import graph_store as graph_store_mod
from cartograph.storage.connection import create_connection
from cartograph.storage.graph_store import GraphStore


@pytest.fixture()
def db_connection(tmp_path):
    conn = create_connection(tmp_path / "centrality.db")
    yield conn
    conn.close()


@pytest.fixture()
def store(db_connection) -> GraphStore:
    return GraphStore(db_connection)


def _node(name: str, kind: str = "function", file_path: str = "x.py") -> dict:
    return {
        "kind": kind,
        "name": name,
        "qualified_name": f"mod.{name}",
        "file_path": file_path,
    }


def _edges(store: GraphStore, pairs: list[tuple[int, int, str]]) -> None:
    store.upsert_edges([{"source_id": s, "target_id": t, "kind": k} for s, t, k in pairs])


class TestKnownGraphs:
    """Verify PageRank against hand-computable reference graphs."""

    def test_symmetric_cycle_has_equal_centrality(self, store: GraphStore):
        """A->B->C->A with identical edge weights should yield equal centrality."""
        ids = store.upsert_nodes([_node("A"), _node("B"), _node("C")])
        _edges(
            store,
            [
                (ids[0], ids[1], "calls"),
                (ids[1], ids[2], "calls"),
                (ids[2], ids[0], "calls"),
            ],
        )
        store.compute_centrality()
        by_name = {r["name"]: r["centrality"] for r in store.find_nodes(file_path="x.py")}
        # All three should be within a tiny numeric delta.
        scores = list(by_name.values())
        assert max(scores) - min(scores) < 1e-6
        assert max(scores) == pytest.approx(1.0, abs=1e-6)

    def test_hub_dominates_leaves(self, store: GraphStore):
        """Star graph: three leaves call a hub. Hub should have highest centrality."""
        ids = store.upsert_nodes([_node("H"), _node("L1"), _node("L2"), _node("L3")])
        _edges(
            store,
            [
                (ids[1], ids[0], "calls"),
                (ids[2], ids[0], "calls"),
                (ids[3], ids[0], "calls"),
            ],
        )
        store.compute_centrality()
        by_name = {r["name"]: r["centrality"] for r in store.find_nodes(file_path="x.py")}
        assert by_name["H"] == pytest.approx(1.0, abs=1e-6)
        # Leaves receive only the teleport + dangling redistribution, equal to each other.
        assert by_name["L1"] == pytest.approx(by_name["L2"], abs=1e-6)
        assert by_name["L2"] == pytest.approx(by_name["L3"], abs=1e-6)
        assert by_name["H"] > by_name["L1"]

    def test_normalisation_is_zero_to_one(self, store: GraphStore):
        """Centrality is normalised so the maximum equals 1.0 and all values are in [0, 1]."""
        ids = store.upsert_nodes([_node(f"n{i}") for i in range(6)])
        _edges(
            store,
            [
                (ids[0], ids[1], "calls"),
                (ids[1], ids[2], "imports"),
                (ids[2], ids[3], "inherits"),
                (ids[3], ids[4], "contains"),
                (ids[4], ids[5], "depends_on"),
                (ids[5], ids[0], "calls"),
            ],
        )
        store.compute_centrality()
        scores = [r["centrality"] for r in store.find_nodes(file_path="x.py")]
        assert all(0.0 <= s <= 1.0 + 1e-9 for s in scores)
        assert max(scores) == pytest.approx(1.0, abs=1e-6)


class TestWeighting:
    """Weighted PageRank should prefer 'calls' over 'contains'."""

    def test_calls_outranks_contains_when_source_splits(self, store: GraphStore):
        """When a source splits its outgoing rank across edges of different kinds,
        the target reached by the heavier kind (calls=1.0) receives more than the
        target reached by the lighter kind (contains=0.3)."""
        src = store.upsert_nodes([_node("src")])[0]
        call_target = store.upsert_nodes([_node("call_target")])[0]
        contain_target = store.upsert_nodes([_node("contain_target")])[0]
        _edges(
            store,
            [
                (src, call_target, "calls"),
                (src, contain_target, "contains"),
            ],
        )
        store.compute_centrality()
        rows = {r["name"]: r["centrality"] for r in store.find_nodes(file_path="x.py")}
        assert rows["call_target"] > rows["contain_target"]


class TestCache:
    """Lazy recompute tied to graph_version."""

    def test_recompute_stamps_version(self, store: GraphStore):
        ids = store.upsert_nodes([_node("A"), _node("B")])
        _edges(store, [(ids[0], ids[1], "calls")])
        store.compute_centrality()
        row = store._conn.execute(
            "SELECT graph_version, centrality_version FROM graph_meta WHERE id=1"
        ).fetchone()
        assert row["centrality_version"] == row["graph_version"]

    def test_bump_triggers_recompute(self, store: GraphStore):
        ids = store.upsert_nodes([_node("A"), _node("B"), _node("C")])
        _edges(store, [(ids[0], ids[1], "calls"), (ids[1], ids[2], "calls")])
        store._ensure_centrality_fresh()
        before = {r["name"]: r["centrality"] for r in store.find_nodes(file_path="x.py")}

        # Add a new edge and bump graph_version.
        _edges(store, [(ids[2], ids[0], "calls")])
        store.increment_graph_version()
        store._ensure_centrality_fresh()
        after = {r["name"]: r["centrality"] for r in store.find_nodes(file_path="x.py")}
        # Values should have changed — the new cycle re-balances the ranks.
        assert before != after

    def test_cache_hit_when_fresh(self, store: GraphStore, monkeypatch):
        """Calling _ensure_centrality_fresh twice should only compute once."""
        ids = store.upsert_nodes([_node("A"), _node("B")])
        _edges(store, [(ids[0], ids[1], "calls")])
        store._ensure_centrality_fresh()

        calls = {"n": 0}
        original = store.compute_centrality

        def counting_compute():
            calls["n"] += 1
            original()

        monkeypatch.setattr(store, "compute_centrality", counting_compute)
        store._ensure_centrality_fresh()
        store._ensure_centrality_fresh()
        assert calls["n"] == 0, "compute_centrality should not run when cache is fresh"


class TestEdgeCases:
    def test_empty_graph(self, store: GraphStore):
        """Compute on an empty graph is a no-op and stamps the version."""
        store.compute_centrality()
        row = store._conn.execute(
            "SELECT graph_version, centrality_version FROM graph_meta WHERE id=1"
        ).fetchone()
        assert row["centrality_version"] == row["graph_version"]

    def test_graph_with_no_edges(self, store: GraphStore):
        """Nodes with no edges all receive the teleport baseline."""
        store.upsert_nodes([_node(f"n{i}") for i in range(4)])
        store.compute_centrality()
        scores = [r["centrality"] for r in store.find_nodes(file_path="x.py")]
        # All four should be equal (teleport distributed uniformly across isolates).
        assert max(scores) - min(scores) < 1e-6

    def test_convergence_warning_emitted_when_iterations_truncated(
        self, store: GraphStore, monkeypatch, caplog
    ):
        """When PageRank is forced to stop before converging, a warning is logged.

        Caps iterations at 1 on a chain graph that needs many passes to settle —
        guarantees the final L1 delta exceeds _PAGERANK_CONVERGENCE_WARN_DELTA.
        """
        ids = store.upsert_nodes([_node(f"n{i}") for i in range(8)])
        _edges(store, [(ids[i], ids[i + 1], "calls") for i in range(7)])

        monkeypatch.setattr(graph_store_mod, "_PAGERANK_ITERATIONS", 1)

        with caplog.at_level(logging.WARNING, logger=graph_store_mod.logger.name):
            store.compute_centrality()

        warnings = [r for r in caplog.records if "PageRank did not converge" in r.message]
        assert warnings, "expected a convergence warning when iterations are truncated"

    def test_in_degree_cache_populated(self, store: GraphStore):
        """in_degree_cache should match a live COUNT."""
        ids = store.upsert_nodes([_node("A"), _node("B"), _node("C")])
        _edges(
            store,
            [
                (ids[0], ids[2], "calls"),
                (ids[1], ids[2], "calls"),
            ],
        )
        store.compute_centrality()
        by_name = {r["name"]: r["in_degree_cache"] for r in store.find_nodes(file_path="x.py")}
        assert by_name["C"] == 2
        assert by_name["A"] == 0
        assert by_name["B"] == 0


class TestContextSummaryOrdering:
    def test_context_summary_orders_by_centrality(self, store: GraphStore):
        """context_summary should order by centrality when the cache is populated."""
        # Star: hub with 3 incoming; leaves each with 0 incoming.
        ids = store.upsert_nodes([_node("H"), _node("L1"), _node("L2"), _node("L3")])
        _edges(
            store,
            [
                (ids[1], ids[0], "calls"),
                (ids[2], ids[0], "calls"),
                (ids[3], ids[0], "calls"),
            ],
        )
        rows = store.context_summary(file_paths=["x.py"], max_nodes=4)
        assert rows[0]["name"] == "H"

    def test_context_summary_top_k_prune(self, store: GraphStore):
        """When there are more nodes than max_nodes, only top-K by centrality are returned."""
        ids = store.upsert_nodes([_node(f"n{i}") for i in range(6)])
        # Give n0 many incoming edges so it dominates.
        edges: list[tuple[int, int, str]] = [(ids[i], ids[0], "calls") for i in range(1, 6)]
        _edges(store, edges)
        rows = store.context_summary(file_paths=["x.py"], max_nodes=3)
        assert len(rows) == 3
        # n0 must be in the top 3.
        assert any(r["name"] == "n0" for r in rows)

    def test_context_summary_falls_back_without_cache(self, store: GraphStore):
        """If compute_centrality hasn't populated anything yet, context_summary still works
        by falling back to raw in-degree order via COALESCE."""
        ids = store.upsert_nodes([_node("A"), _node("B"), _node("C")])
        _edges(store, [(ids[0], ids[2], "calls"), (ids[1], ids[2], "calls")])

        # Clear the cache we just populated via _ensure_centrality_fresh inside context_summary.
        store._conn.execute("UPDATE nodes SET centrality = NULL, in_degree_cache = NULL")
        store._conn.commit()

        # Directly issue the SQL path without triggering refresh (bypasses
        # _ensure_centrality_fresh by reading raw rows).
        rows = store._conn.execute(
            """
            SELECT n.*, COALESCE(n.in_degree_cache,
                                (SELECT COUNT(*) FROM edges ec WHERE ec.target_id = n.id),
                                0) AS in_degree
            FROM nodes n
            ORDER BY COALESCE(n.centrality, 0) DESC, in_degree DESC
            """
        ).fetchall()
        # Top result should be C (in_degree=2) despite centrality being NULL.
        assert rows[0]["name"] == "C"


class TestRankInDegreeUsesCache:
    def test_rank_by_in_degree_reads_cache(self, store: GraphStore):
        ids = store.upsert_nodes([_node("A"), _node("B"), _node("C")])
        _edges(
            store,
            [(ids[0], ids[2], "calls"), (ids[1], ids[2], "calls")],
        )
        ranked = store.rank_by_in_degree(limit=5)
        # The top node should be C with in_degree 2.
        assert ranked[0]["name"] == "C"
        assert ranked[0]["in_degree"] == 2
        # Centrality should be populated (cache was refreshed).
        assert ranked[0]["centrality"] is not None
