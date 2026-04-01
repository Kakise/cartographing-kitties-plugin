"""Tests for the Cartograph SQLite graph store."""

from __future__ import annotations

import time

import pytest

from cartograph.storage.connection import create_connection
from cartograph.storage.graph_store import GraphStore


@pytest.fixture()
def db_connection(tmp_path):
    """Create a fresh SQLite connection for each test."""
    conn = create_connection(tmp_path / "test.db")
    yield conn
    conn.close()


@pytest.fixture()
def graph_store(db_connection):
    """Create a GraphStore wrapping the test connection."""
    return GraphStore(db_connection)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _make_node(name: str, kind: str = "function", file_path: str = "src/mod.py", **kw):
    return {
        "kind": kind,
        "name": name,
        "qualified_name": kw.pop("qualified_name", f"mod.{name}"),
        "file_path": file_path,
        "start_line": kw.pop("start_line", 1),
        "end_line": kw.pop("end_line", 10),
        "language": kw.pop("language", "python"),
        "summary": kw.pop("summary", None),
        "annotation_status": kw.pop("annotation_status", "pending"),
        "content_hash": kw.pop("content_hash", None),
        "properties": kw.pop("properties", None),
        **kw,
    }


# ------------------------------------------------------------------
# 1. Insert nodes and edges, query them back
# ------------------------------------------------------------------


class TestBasicCRUD:
    def test_insert_and_query_nodes(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes([_make_node("foo"), _make_node("bar")])
        assert len(ids) == 2

        node = graph_store.get_node(ids[0])
        assert node is not None
        assert node["name"] == "foo"

        node2 = graph_store.get_node_by_name("mod.bar")
        assert node2 is not None
        assert node2["name"] == "bar"

    def test_insert_and_query_edges(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes([_make_node("a"), _make_node("b")])
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls", "weight": 1.0},
            ]
        )
        edges = graph_store.get_edges(source_id=ids[0])
        assert len(edges) == 1
        assert edges[0]["kind"] == "calls"

    def test_find_nodes_by_kind(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("f1", kind="function"),
                _make_node("C1", kind="class", qualified_name="mod.C1"),
            ]
        )
        funcs = graph_store.find_nodes(kind="function")
        assert len(funcs) == 1
        assert funcs[0]["name"] == "f1"

    def test_find_nodes_by_file_path(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("a", file_path="a.py", qualified_name="a.a"),
                _make_node("b", file_path="b.py", qualified_name="b.b"),
            ]
        )
        results = graph_store.find_nodes(file_path="a.py")
        assert len(results) == 1
        assert results[0]["name"] == "a"


# ------------------------------------------------------------------
# 2. Transitive dependency: A->B->C
# ------------------------------------------------------------------


class TestTransitiveDependency:
    def test_forward_traversal(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
                _make_node("C", qualified_name="mod.C"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[1], "target_id": ids[2], "kind": "calls"},
            ]
        )
        deps = graph_store.transitive_dependencies(ids[0])
        names = {d["name"] for d in deps}
        assert names == {"B", "C"}
        # Check depths
        depth_map = {d["name"]: d["depth"] for d in deps}
        assert depth_map["B"] == 1
        assert depth_map["C"] == 2


# ------------------------------------------------------------------
# 3. Reverse dependency (impact analysis)
# ------------------------------------------------------------------


class TestReverseDependency:
    def test_impact_analysis(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
                _make_node("C", qualified_name="mod.C"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[2], "kind": "calls"},
                {"source_id": ids[1], "target_id": ids[2], "kind": "calls"},
            ]
        )
        rdeps = graph_store.reverse_dependencies(ids[2])
        names = {d["name"] for d in rdeps}
        assert names == {"A", "B"}


# ------------------------------------------------------------------
# 4. Cycle safety: A->B->A does not infinite-recurse
# ------------------------------------------------------------------


class TestCycleSafety:
    def test_cycle_does_not_hang(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[1], "target_id": ids[0], "kind": "calls"},
            ]
        )
        deps = graph_store.transitive_dependencies(ids[0])
        names = {d["name"] for d in deps}
        # Both reachable, but no infinite loop
        assert names == {"A", "B"}


# ------------------------------------------------------------------
# 5. FTS5 search
# ------------------------------------------------------------------


class TestFTS5Search:
    def test_search_by_keyword(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("parse_json", summary="Parse a JSON document into a tree"),
                _make_node(
                    "format_xml", summary="Format an XML document", qualified_name="mod.format_xml"
                ),
            ]
        )
        results = graph_store.search("JSON")
        assert len(results) >= 1
        assert results[0]["name"] == "parse_json"

    def test_search_by_name(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("calculate_total", summary="Sum line items"),
            ]
        )
        results = graph_store.search("calculate_total")
        assert len(results) == 1


# ------------------------------------------------------------------
# 6. FTS5 sync: update reflects in search
# ------------------------------------------------------------------


class TestFTS5Sync:
    def test_update_reflects_in_search(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("worker", summary="Background worker process"),
            ]
        )
        # Verify initial search works
        assert len(graph_store.search("worker")) >= 1

        # Update the summary
        graph_store.upsert_nodes(
            [
                _make_node("worker", summary="Celery task runner"),
            ]
        )
        # Old keyword should not match summary anymore, but name still matches
        results_old = graph_store.search("Background")
        old_summaries = [r["summary"] for r in results_old if r["name"] == "worker"]
        assert all(s == "Celery task runner" for s in old_summaries) or len(old_summaries) == 0

        # New keyword should match
        results_new = graph_store.search("Celery")
        assert any(r["name"] == "worker" for r in results_new)


# ------------------------------------------------------------------
# 7. Batch insert performance
# ------------------------------------------------------------------


class TestBatchPerformance:
    def test_5000_nodes_15000_edges_under_5s(self, graph_store: GraphStore):
        nodes = [
            _make_node(
                f"func_{i}",
                qualified_name=f"mod.func_{i}",
                file_path=f"src/file_{i % 100}.py",
            )
            for i in range(5_000)
        ]
        start = time.perf_counter()
        ids = graph_store.bulk_insert_nodes(nodes)
        assert len(ids) == 5_000

        edge_kinds = ["calls", "imports", "depends_on"]
        edges = [
            {
                "source_id": ids[i % 5_000],
                "target_id": ids[(i + 1) % 5_000],
                "kind": edge_kinds[i % 3],
            }
            for i in range(15_000)
        ]
        graph_store.bulk_insert_edges(edges)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"Batch insert took {elapsed:.2f}s (limit 5s)"


# ------------------------------------------------------------------
# 8. WAL mode
# ------------------------------------------------------------------


class TestWALMode:
    def test_wal_mode_is_set(self, db_connection):
        cur = db_connection.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        assert mode == "wal"


# ------------------------------------------------------------------
# 9. Delete file nodes (cascading)
# ------------------------------------------------------------------


class TestDeleteFileNodes:
    def test_delete_removes_nodes_and_edges(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("a", file_path="target.py", qualified_name="target.a"),
                _make_node("b", file_path="target.py", qualified_name="target.b"),
                _make_node("c", file_path="other.py", qualified_name="other.c"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[2], "target_id": ids[0], "kind": "calls"},
            ]
        )
        deleted = graph_store.delete_file_nodes("target.py")
        assert deleted == 2

        # Nodes gone
        assert graph_store.get_node(ids[0]) is None
        assert graph_store.get_node(ids[1]) is None
        # Remaining node still exists
        assert graph_store.get_node(ids[2]) is not None
        # Edges involving deleted nodes are gone (cascade)
        assert graph_store.get_edges(source_id=ids[2]) == []


# ------------------------------------------------------------------
# 10. Content hash comparison
# ------------------------------------------------------------------


class TestContentHash:
    def test_detect_changed_files(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node(
                    "f", kind="file", file_path="a.py", qualified_name="a.py", content_hash="abc123"
                ),
                _make_node(
                    "g", kind="file", file_path="b.py", qualified_name="b.py", content_hash="def456"
                ),
            ]
        )
        hashes = graph_store.get_content_hashes()
        assert hashes == {"a.py": "abc123", "b.py": "def456"}

        # Simulate a change
        new_hashes = {"a.py": "abc123", "b.py": "changed!"}
        changed = {fp for fp, h in new_hashes.items() if hashes.get(fp) != h}
        assert changed == {"b.py"}


# ------------------------------------------------------------------
# 11. Upsert: same qualified_name updates, no duplication
# ------------------------------------------------------------------


class TestUpsert:
    def test_upsert_updates_existing(self, graph_store: GraphStore):
        graph_store.upsert_nodes([_make_node("x", summary="v1")])
        graph_store.upsert_nodes([_make_node("x", summary="v2")])

        results = graph_store.find_nodes(name="x")
        assert len(results) == 1
        assert results[0]["summary"] == "v2"


# ------------------------------------------------------------------
# 12. Re-index preserves annotations
# ------------------------------------------------------------------


class TestReindexPreservesAnnotations:
    def test_upsert_preserves_annotated_status_on_reindex(self, graph_store: GraphStore):
        """Re-indexing (default annotation_status='pending') must not reset
        nodes that are already 'annotated'."""
        # Insert an annotated node (simulates agent annotation).
        graph_store.upsert_nodes(
            [
                _make_node(
                    "svc",
                    summary="Handles auth",
                    annotation_status="annotated",
                    properties={"tags": ["auth"], "role": "service"},
                ),
            ]
        )
        node = graph_store.get_node_by_name("mod.svc")
        assert node is not None
        assert node["annotation_status"] == "annotated"

        # Simulate re-index: upsert with default annotation_status (pending).
        # The indexer doesn't pass annotation_status, so it defaults to pending.
        graph_store.upsert_nodes(
            [
                _make_node("svc"),
            ]
        )

        # Annotation should be preserved.
        node = graph_store.get_node_by_name("mod.svc")
        assert node is not None
        assert node["annotation_status"] == "annotated"
        assert node["summary"] == "Handles auth"

    def test_upsert_applies_explicit_annotated_status(self, graph_store: GraphStore):
        """Explicitly passing annotation_status='annotated' should still work."""
        graph_store.upsert_nodes([_make_node("x")])
        assert graph_store.get_node_by_name("mod.x")["annotation_status"] == "pending"

        graph_store.upsert_nodes(
            [
                _make_node("x", summary="annotated", annotation_status="annotated"),
            ]
        )
        assert graph_store.get_node_by_name("mod.x")["annotation_status"] == "annotated"


# ------------------------------------------------------------------
# 13. Stale annotation detection
# ------------------------------------------------------------------


class TestFindStaleNodes:
    def test_no_stale_when_no_annotated_nodes(self, graph_store: GraphStore):
        graph_store.upsert_nodes([_make_node("a", content_hash="abc")])
        assert graph_store.find_stale_nodes() == []

    def test_annotated_with_matching_hash_not_stale(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node(
                    "a",
                    annotation_status="annotated",
                    content_hash="abc",
                    annotated_content_hash="abc",
                ),
            ]
        )
        assert graph_store.find_stale_nodes() == []

    def test_annotated_with_different_hash_is_stale(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node(
                    "a",
                    annotation_status="annotated",
                    content_hash="new_hash",
                    annotated_content_hash="old_hash",
                ),
            ]
        )
        stale = graph_store.find_stale_nodes()
        assert len(stale) == 1
        assert stale[0]["name"] == "a"

    def test_annotated_with_null_annotated_hash_is_stale(self, graph_store: GraphStore):
        """Pre-migration nodes with annotated_content_hash=NULL are stale."""
        graph_store.upsert_nodes(
            [
                _make_node(
                    "a",
                    annotation_status="annotated",
                    content_hash="abc",
                    annotated_content_hash=None,
                ),
            ]
        )
        stale = graph_store.find_stale_nodes()
        assert len(stale) == 1

    def test_pending_nodes_not_stale(self, graph_store: GraphStore):
        """Pending nodes are never stale regardless of hashes."""
        graph_store.upsert_nodes(
            [
                _make_node("a", annotation_status="pending", content_hash="x", annotated_content_hash="y"),
            ]
        )
        assert graph_store.find_stale_nodes() == []

    def test_annotated_without_content_hash_not_stale(self, graph_store: GraphStore):
        """Annotated nodes with NULL content_hash are not stale (no basis for comparison)."""
        graph_store.upsert_nodes(
            [
                _make_node("a", annotation_status="annotated", content_hash=None),
            ]
        )
        assert graph_store.find_stale_nodes() == []

    def test_file_paths_filter(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node(
                    "a",
                    file_path="a.py",
                    qualified_name="mod_a.a",
                    annotation_status="annotated",
                    content_hash="new",
                    annotated_content_hash="old",
                ),
                _make_node(
                    "b",
                    file_path="b.py",
                    qualified_name="mod_b.b",
                    annotation_status="annotated",
                    content_hash="new",
                    annotated_content_hash="old",
                ),
            ]
        )
        stale = graph_store.find_stale_nodes(file_paths=["a.py"])
        assert len(stale) == 1
        assert stale[0]["name"] == "a"

    def test_limit(self, graph_store: GraphStore):
        for i in range(5):
            graph_store.upsert_nodes(
                [
                    _make_node(
                        f"n{i}",
                        qualified_name=f"mod.n{i}",
                        annotation_status="annotated",
                        content_hash="new",
                        annotated_content_hash="old",
                    ),
                ]
            )
        stale = graph_store.find_stale_nodes(limit=3)
        assert len(stale) == 3


# ------------------------------------------------------------------
# Ranking
# ------------------------------------------------------------------


class TestRankByInDegree:
    def test_ranks_by_incoming_edges(self, graph_store: GraphStore):
        """Node with more incoming edges should rank higher."""
        ids = graph_store.upsert_nodes(
            [
                _make_node("popular", qualified_name="mod.popular"),
                _make_node("caller1", qualified_name="mod.caller1"),
                _make_node("caller2", qualified_name="mod.caller2"),
                _make_node("lonely", qualified_name="mod.lonely"),
            ]
        )
        # Two edges pointing to 'popular', none to 'lonely'.
        graph_store.upsert_edges(
            [
                {"source_id": ids[1], "target_id": ids[0], "kind": "calls"},
                {"source_id": ids[2], "target_id": ids[0], "kind": "calls"},
            ]
        )
        ranked = graph_store.rank_by_in_degree()
        assert ranked[0]["name"] == "popular"
        assert ranked[0]["in_degree"] == 2
        assert ranked[0]["out_degree"] == 0

    def test_isolated_node_has_zero_in_degree(self, graph_store: GraphStore):
        graph_store.upsert_nodes([_make_node("solo", qualified_name="mod.solo")])
        ranked = graph_store.rank_by_in_degree()
        assert len(ranked) == 1
        assert ranked[0]["in_degree"] == 0

    def test_kind_filter(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("MyClass", kind="class", qualified_name="mod.MyClass"),
                _make_node("my_func", kind="function", qualified_name="mod.my_func"),
            ]
        )
        ranked = graph_store.rank_by_in_degree(kind="class")
        assert len(ranked) == 1
        assert ranked[0]["name"] == "MyClass"

    def test_scope_file_paths(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("a", file_path="a.py", qualified_name="a.a"),
                _make_node("b", file_path="b.py", qualified_name="b.b"),
            ]
        )
        ranked = graph_store.rank_by_in_degree(scope_file_paths=["a.py"])
        assert len(ranked) == 1
        assert ranked[0]["name"] == "a"

    def test_limit(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node(f"f{i}", qualified_name=f"mod.f{i}")
                for i in range(10)
            ]
        )
        ranked = graph_store.rank_by_in_degree(limit=3)
        assert len(ranked) == 3

    def test_out_degree_computed(self, graph_store: GraphStore):
        """out_degree subquery should count outgoing edges."""
        ids = graph_store.upsert_nodes(
            [
                _make_node("hub", qualified_name="mod.hub"),
                _make_node("t1", qualified_name="mod.t1"),
                _make_node("t2", qualified_name="mod.t2"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[0], "target_id": ids[2], "kind": "calls"},
            ]
        )
        ranked = graph_store.rank_by_in_degree()
        hub = next(r for r in ranked if r["name"] == "hub")
        assert hub["out_degree"] == 2


class TestRankByTransitive:
    def test_transitive_ranking(self, graph_store: GraphStore):
        """A -> B -> C: C has 2 transitive dependents, B has 1."""
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
                _make_node("C", qualified_name="mod.C"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[1], "target_id": ids[2], "kind": "calls"},
            ]
        )
        ranked = graph_store.rank_by_transitive(
            scope_qnames=["mod.B", "mod.C"]
        )
        assert ranked[0]["name"] == "C"
        assert ranked[0]["transitive_count"] == 2
        assert ranked[1]["name"] == "B"
        assert ranked[1]["transitive_count"] == 1


# ------------------------------------------------------------------
# Context summary
# ------------------------------------------------------------------


class TestContextSummary:
    def test_returns_nodes_with_in_degree(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A", file_path="src/a.py"),
                _make_node("B", qualified_name="mod.B", file_path="src/a.py"),
                _make_node("C", qualified_name="mod.C", file_path="src/b.py"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[2], "target_id": ids[1], "kind": "calls"},
            ]
        )
        rows = graph_store.context_summary()
        assert len(rows) == 3
        b_row = next(r for r in rows if r["name"] == "B")
        assert b_row["in_degree"] == 2
        a_row = next(r for r in rows if r["name"] == "A")
        assert a_row["in_degree"] == 0

    def test_filter_by_file_paths(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A", file_path="src/a.py"),
                _make_node("B", qualified_name="mod.B", file_path="src/b.py"),
            ]
        )
        rows = graph_store.context_summary(file_paths=["src/a.py"])
        assert len(rows) == 1
        assert rows[0]["name"] == "A"

    def test_filter_by_qualified_names(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
            ]
        )
        rows = graph_store.context_summary(qualified_names=["mod.A"])
        assert len(rows) == 1
        assert rows[0]["qualified_name"] == "mod.A"

    def test_max_nodes_limits_output(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
                _make_node("C", qualified_name="mod.C"),
            ]
        )
        rows = graph_store.context_summary(max_nodes=2)
        assert len(rows) == 2

    def test_ordered_by_in_degree_descending(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("A", qualified_name="mod.A"),
                _make_node("B", qualified_name="mod.B"),
            ]
        )
        # B has 1 incoming edge, A has 0.
        graph_store.upsert_edges(
            [{"source_id": ids[0], "target_id": ids[1], "kind": "calls"}]
        )
        rows = graph_store.context_summary()
        assert rows[0]["name"] == "B"
        assert rows[0]["in_degree"] == 1
        assert rows[1]["name"] == "A"
        assert rows[1]["in_degree"] == 0


# ------------------------------------------------------------------
# Snapshot and diff
# ------------------------------------------------------------------


class TestSnapshotNodes:
    def test_snapshot_all_nodes(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("a", qualified_name="mod.a", content_hash="h1"),
                _make_node("b", qualified_name="mod.b", content_hash="h2"),
            ]
        )
        snap = graph_store.snapshot_nodes()
        assert len(snap) == 2
        assert "mod.a" in snap
        assert snap["mod.a"]["content_hash"] == "h1"

    def test_snapshot_filtered_by_file_paths(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                _make_node("a", file_path="a.py", qualified_name="a.a", content_hash="h1"),
                _make_node("b", file_path="b.py", qualified_name="b.b", content_hash="h2"),
            ]
        )
        snap = graph_store.snapshot_nodes(file_paths=["a.py"])
        assert len(snap) == 1
        assert "a.a" in snap

    def test_snapshot_empty_db(self, graph_store: GraphStore):
        snap = graph_store.snapshot_nodes()
        assert snap == {}


class TestSnapshotEdges:
    def test_snapshot_all_edges(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("a", qualified_name="mod.a"),
                _make_node("b", qualified_name="mod.b"),
            ]
        )
        graph_store.upsert_edges(
            [{"source_id": ids[0], "target_id": ids[1], "kind": "calls"}]
        )
        edges = graph_store.snapshot_edges()
        assert len(edges) == 1
        assert edges[0]["source"] == "mod.a"
        assert edges[0]["target"] == "mod.b"
        assert edges[0]["kind"] == "calls"

    def test_snapshot_edges_filtered_by_file_paths(self, graph_store: GraphStore):
        ids = graph_store.upsert_nodes(
            [
                _make_node("a", file_path="a.py", qualified_name="a.a"),
                _make_node("b", file_path="b.py", qualified_name="b.b"),
                _make_node("c", file_path="c.py", qualified_name="c.c"),
            ]
        )
        graph_store.upsert_edges(
            [
                {"source_id": ids[0], "target_id": ids[1], "kind": "calls"},
                {"source_id": ids[1], "target_id": ids[2], "kind": "calls"},
            ]
        )
        edges = graph_store.snapshot_edges(file_paths=["a.py"])
        # Should include the edge from a.py -> b.py (a.py is an endpoint).
        assert len(edges) == 1
        assert edges[0]["source"] == "a.a"


class TestComputeDiff:
    def test_nodes_added(self, graph_store: GraphStore):
        before: dict[str, dict] = {}
        after = {"mod.a": {"kind": "function", "name": "a", "file_path": "a.py", "content_hash": "h1"}}
        diff = graph_store.compute_diff(before, after, [], [])
        assert len(diff["nodes_added"]) == 1
        assert diff["nodes_added"][0]["qualified_name"] == "mod.a"
        assert diff["summary"]["nodes_added"] == 1

    def test_nodes_removed(self, graph_store: GraphStore):
        before = {"mod.a": {"kind": "function", "name": "a", "file_path": "a.py", "content_hash": "h1"}}
        after: dict[str, dict] = {}
        diff = graph_store.compute_diff(before, after, [], [])
        assert len(diff["nodes_removed"]) == 1
        assert diff["nodes_removed"][0]["qualified_name"] == "mod.a"
        assert diff["summary"]["nodes_removed"] == 1

    def test_nodes_modified(self, graph_store: GraphStore):
        before = {"mod.a": {"kind": "function", "name": "a", "file_path": "a.py", "content_hash": "h1"}}
        after = {"mod.a": {"kind": "function", "name": "a", "file_path": "a.py", "content_hash": "h2"}}
        diff = graph_store.compute_diff(before, after, [], [])
        assert len(diff["nodes_modified"]) == 1
        assert diff["nodes_modified"][0]["changes"] == ["content_hash_changed"]
        assert diff["summary"]["nodes_modified"] == 1

    def test_unchanged_nodes_not_in_diff(self, graph_store: GraphStore):
        node = {"kind": "function", "name": "a", "file_path": "a.py", "content_hash": "h1"}
        before = {"mod.a": node}
        after = {"mod.a": dict(node)}
        diff = graph_store.compute_diff(before, after, [], [])
        assert len(diff["nodes_modified"]) == 0

    def test_edges_added_and_removed(self, graph_store: GraphStore):
        before_edges = [{"source": "mod.a", "target": "mod.b", "kind": "calls"}]
        after_edges = [{"source": "mod.a", "target": "mod.c", "kind": "calls"}]
        diff = graph_store.compute_diff({}, {}, before_edges, after_edges)
        assert len(diff["edges_added"]) == 1
        assert diff["edges_added"][0]["target"] == "mod.c"
        assert len(diff["edges_removed"]) == 1
        assert diff["edges_removed"][0]["target"] == "mod.b"

    def test_empty_diff(self, graph_store: GraphStore):
        diff = graph_store.compute_diff({}, {}, [], [])
        assert diff["summary"]["nodes_added"] == 0
        assert diff["summary"]["nodes_removed"] == 0
        assert diff["summary"]["nodes_modified"] == 0
        assert diff["summary"]["edges_added"] == 0
        assert diff["summary"]["edges_removed"] == 0


# ------------------------------------------------------------------
# Validate nodes
# ------------------------------------------------------------------


class TestValidateNodes:
    def test_clean_graph_no_issues(self, graph_store: GraphStore):
        """A well-formed graph produces no issues."""
        ids = graph_store.upsert_nodes(
            [
                _make_node("file", kind="file", qualified_name="file::a.py", file_path="a.py"),
                _make_node("fn", qualified_name="mod.fn", file_path="a.py"),
            ]
        )
        graph_store.upsert_edges(
            [{"source_id": ids[0], "target_id": ids[1], "kind": "contains"}]
        )
        issues = graph_store.validate_nodes()
        assert issues == []

    def test_orphan_nodes_detected(self, graph_store: GraphStore):
        """Non-file node with no incoming edges is an orphan."""
        graph_store.upsert_nodes([_make_node("orphan", qualified_name="mod.orphan")])
        issues = graph_store.validate_nodes(checks=["orphan_nodes"])
        assert len(issues) == 1
        assert issues[0]["check"] == "orphan_nodes"
        assert issues[0]["node"] == "mod.orphan"
        assert issues[0]["severity"] == "warning"

    def test_file_nodes_not_orphans(self, graph_store: GraphStore):
        """File and module nodes are excluded from orphan check."""
        graph_store.upsert_nodes(
            [
                _make_node("f", kind="file", qualified_name="file::f.py", file_path="f.py"),
                _make_node("m", kind="module", qualified_name="mod.m", file_path="f.py"),
            ]
        )
        issues = graph_store.validate_nodes(checks=["orphan_nodes"])
        assert issues == []

    def test_stale_annotations_detected(self, graph_store: GraphStore):
        """Annotated node with mismatched content_hash is stale."""
        graph_store.upsert_nodes(
            [
                _make_node(
                    "stale",
                    qualified_name="mod.stale",
                    annotation_status="annotated",
                    content_hash="new",
                    annotated_content_hash="old",
                )
            ]
        )
        issues = graph_store.validate_nodes(checks=["stale_annotations"])
        assert len(issues) == 1
        assert issues[0]["check"] == "stale_annotations"
        assert issues[0]["node"] == "mod.stale"
        assert issues[0]["severity"] == "warning"

    def test_stale_annotations_null_annotated_hash(self, graph_store: GraphStore):
        """Pre-migration node with NULL annotated_content_hash is stale."""
        graph_store.upsert_nodes(
            [
                _make_node(
                    "old",
                    qualified_name="mod.old",
                    annotation_status="annotated",
                    content_hash="abc",
                    annotated_content_hash=None,
                )
            ]
        )
        issues = graph_store.validate_nodes(checks=["stale_annotations"])
        assert len(issues) == 1
        assert issues[0]["node"] == "mod.old"

    def test_matching_hash_not_stale(self, graph_store: GraphStore):
        """Annotated node with matching hashes is not stale."""
        graph_store.upsert_nodes(
            [
                _make_node(
                    "fresh",
                    qualified_name="mod.fresh",
                    annotation_status="annotated",
                    content_hash="same",
                    annotated_content_hash="same",
                )
            ]
        )
        issues = graph_store.validate_nodes(checks=["stale_annotations"])
        assert issues == []

    def test_dangling_edges_detected(self, graph_store: GraphStore):
        """Edges referencing non-existent nodes are dangling."""
        ids = graph_store.upsert_nodes(
            [
                _make_node("a", qualified_name="mod.a"),
                _make_node("b", qualified_name="mod.b"),
            ]
        )
        graph_store.upsert_edges(
            [{"source_id": ids[0], "target_id": ids[1], "kind": "calls"}]
        )
        # Bypass FK by disabling enforcement temporarily and deleting a node.
        graph_store._conn.execute("PRAGMA foreign_keys = OFF")
        graph_store._conn.execute("DELETE FROM nodes WHERE id = ?", (ids[1],))
        graph_store._conn.commit()
        graph_store._conn.execute("PRAGMA foreign_keys = ON")

        issues = graph_store.validate_nodes(checks=["dangling_edges"])
        assert len(issues) == 1
        assert issues[0]["check"] == "dangling_edges"
        assert issues[0]["severity"] == "error"

    def test_scope_file_paths(self, graph_store: GraphStore):
        """File path scope limits orphan check."""
        graph_store.upsert_nodes(
            [
                _make_node("a", file_path="a.py", qualified_name="a.a"),
                _make_node("b", file_path="b.py", qualified_name="b.b"),
            ]
        )
        issues = graph_store.validate_nodes(file_paths=["a.py"], checks=["orphan_nodes"])
        nodes = [i["node"] for i in issues]
        assert "a.a" in nodes
        assert "b.b" not in nodes

    def test_scope_qualified_names(self, graph_store: GraphStore):
        """Qualified name scope limits stale check."""
        graph_store.upsert_nodes(
            [
                _make_node(
                    "a",
                    qualified_name="mod.a",
                    annotation_status="annotated",
                    content_hash="new",
                    annotated_content_hash="old",
                ),
                _make_node(
                    "b",
                    qualified_name="mod.b",
                    annotation_status="annotated",
                    content_hash="new",
                    annotated_content_hash="old",
                ),
            ]
        )
        issues = graph_store.validate_nodes(
            qualified_names=["mod.a"], checks=["stale_annotations"]
        )
        nodes = [i["node"] for i in issues]
        assert "mod.a" in nodes
        assert "mod.b" not in nodes

    def test_checks_filter(self, graph_store: GraphStore):
        """Only requested checks are run."""
        graph_store.upsert_nodes([_make_node("orphan", qualified_name="mod.orphan")])
        # Only run stale_annotations — should not find the orphan.
        issues = graph_store.validate_nodes(checks=["stale_annotations"])
        assert all(i["check"] == "stale_annotations" for i in issues)

    def test_all_checks_run_by_default(self, graph_store: GraphStore):
        """None checks means all three run."""
        issues = graph_store.validate_nodes()
        # No issues on empty graph, but the method should not error.
        assert isinstance(issues, list)
