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
