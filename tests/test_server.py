"""Tests for the Cartograph MCP server tools."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# The tool modules read state from cartograph.server.main module-level vars.
import cartograph.server.main as server_main
from cartograph.compat import StoragePaths
from cartograph.indexing import Indexer
from cartograph.server.tools.analysis import find_dependencies, find_dependents, rank_nodes
from cartograph.server.tools.annotate import (
    find_low_quality_annotations,
    find_stale_annotations,
    get_pending_annotations,
    requeue_low_quality_annotations,
    submit_annotations,
)
from cartograph.server.tools.index import annotation_status, index_codebase
from cartograph.server.tools.memory import (
    add_litter_box_entry,
    add_treat_box_entry,
    query_litter_box,
    query_treat_box,
)
from cartograph.server.tools.query import (
    batch_query_nodes,
    get_context_summary,
    get_file_structure,
    query_node,
    search,
)
from cartograph.server.tools.reactive import graph_diff, validate_graph
from cartograph.storage import GraphStore, create_connection

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"


@pytest.fixture()
def graph_store(tmp_path: Path):
    """Create a GraphStore backed by a temp database and wire it into server state."""
    data_dir = tmp_path / ".pawprints"
    data_dir.mkdir()
    db_path = data_dir / "graph.db"
    conn = create_connection(db_path)
    store = GraphStore(conn)

    # Wire module-level state so tools can find it.
    server_main._store = store
    server_main._root = FIXTURE_DIR.resolve()
    server_main._storage_paths = StoragePaths(
        project_root=FIXTURE_DIR.resolve(),
        storage_root=FIXTURE_DIR.resolve(),
        data_dir=data_dir,
        db_path=db_path,
        treat_box_path=data_dir / "treat-box.md",
        litter_box_path=data_dir / "litter-box.md",
    )

    yield store

    store.close()
    server_main._store = None
    server_main._root = None
    server_main._storage_paths = None
    server_main._last_diff = None


@pytest.fixture()
def indexed_store(graph_store: GraphStore):
    """Return a GraphStore that has already indexed the sample project."""
    indexer = Indexer(FIXTURE_DIR, graph_store)
    indexer.index_all()
    return graph_store


# ------------------------------------------------------------------
# Tool tests
# ------------------------------------------------------------------


class TestIndexCodebase:
    def test_index_codebase_returns_stats(self, graph_store: GraphStore):
        result = index_codebase(full=True)
        assert "error" not in result
        assert result["files_parsed"] > 0
        assert result["nodes_created"] > 0

    def test_index_codebase_incremental(self, indexed_store: GraphStore):
        result = index_codebase(full=False)
        assert "error" not in result
        # Incremental on already-indexed project should parse 0 new files.
        assert result["files_parsed"] == 0


class TestMemoryExports:
    def test_add_litter_box_entry_without_server_state_returns_error(self):
        original_store = server_main._store
        original_paths = server_main._storage_paths
        server_main._store = None
        server_main._storage_paths = None
        try:
            result = add_litter_box_entry("failure", "Missing state")
        finally:
            server_main._store = original_store
            server_main._storage_paths = original_paths

        assert result == {"error": "Server not initialised"}

    def test_add_treat_box_entry_exports_to_resolved_storage_path(self, graph_store: GraphStore):
        result = add_treat_box_entry("best-practice", "Use isolated storage roots")
        assert "error" not in result
        assert result["exported_to"].endswith("treat-box.md")
        assert Path(result["exported_to"]).exists()

    def test_add_litter_box_entry_exports_to_resolved_storage_path(self, graph_store: GraphStore):
        result = add_litter_box_entry("anti-pattern", "Share one SQLite DB across repos")
        assert "error" not in result
        assert result["exported_to"].endswith("litter-box.md")
        assert Path(result["exported_to"]).exists()

    def test_add_treat_box_entry_without_server_state_returns_error(self):
        original_store = server_main._store
        original_paths = server_main._storage_paths
        server_main._store = None
        server_main._storage_paths = None
        try:
            result = add_treat_box_entry("best-practice", "Missing state")
        finally:
            server_main._store = original_store
            server_main._storage_paths = original_paths

        assert result == {"error": "Server not initialised"}

    def test_add_litter_box_entry_invalid_category_returns_error(self, graph_store: GraphStore):
        result = add_litter_box_entry("bad-category", "Nope")
        assert "bad-category" in result["error"]

    def test_query_treat_box_returns_entries(self, graph_store: GraphStore):
        add_treat_box_entry("best-practice", "Use the centralized root")

        result = query_treat_box(search="centralized")

        assert result["count"] == 1
        assert result["entries"][0]["description"] == "Use the centralized root"

    def test_query_litter_box_returns_entries(self, graph_store: GraphStore):
        add_litter_box_entry("failure", "Do not merge project databases")

        result = query_litter_box(search="merge")

        assert result["count"] == 1
        assert result["entries"][0]["description"] == "Do not merge project databases"

    def test_query_treat_box_without_store_returns_error(self):
        original_store = server_main._store
        server_main._store = None
        try:
            result = query_treat_box()
        finally:
            server_main._store = original_store

        assert result == {"error": "Server not initialised"}

    def test_query_litter_box_without_store_returns_error(self):
        original_store = server_main._store
        server_main._store = None
        try:
            result = query_litter_box()
        finally:
            server_main._store = original_store

        assert result == {"error": "Server not initialised"}

    def test_query_litter_box_handles_query_errors(self, graph_store: GraphStore, monkeypatch):
        monkeypatch.setattr(
            "cartograph.memory.query_entries",
            lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("query failed")),
        )

        result = query_litter_box()

        assert result == {"error": "query failed"}

    def test_add_treat_box_entry_handles_validation_errors(self, graph_store: GraphStore):
        result = add_treat_box_entry("bad-category", "Nope")
        assert "bad-category" in result["error"]

    def test_query_treat_box_handles_query_errors(self, graph_store: GraphStore, monkeypatch):
        monkeypatch.setattr(
            "cartograph.memory.query_entries",
            lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("query failed")),
        )

        result = query_treat_box()

        assert result == {"error": "query failed"}


class TestQueryNode:
    def test_query_known_node(self, indexed_store: GraphStore):
        result = query_node("User")
        assert result["found"] is True
        assert result["node"]["name"] == "User"
        assert isinstance(result["neighbors"], list)

    def test_query_by_qualified_name(self, indexed_store: GraphStore):
        result = query_node("models.user::User")
        assert result["found"] is True
        assert result["node"]["qualified_name"] == "models.user::User"

    def test_query_nonexistent_node(self, indexed_store: GraphStore):
        result = query_node("NonExistentClassName")
        assert result["found"] is False

    def test_query_node_has_neighbors(self, indexed_store: GraphStore):
        result = query_node("UserService")
        assert result["found"] is True
        # UserService should have at least some edges (contains, etc.)
        assert len(result["neighbors"]) > 0


class TestFindDependencies:
    def test_find_dependencies(self, indexed_store: GraphStore):
        # The file node for main.py should import user_service
        result = find_dependencies("file::src/main.py")
        assert result["found"] is True
        assert isinstance(result["dependencies"], list)

    def test_find_dependencies_nonexistent(self, indexed_store: GraphStore):
        result = find_dependencies("NonExistent")
        assert result["found"] is False


class TestFindDependents:
    def test_find_dependents(self, indexed_store: GraphStore):
        result = find_dependents("file::src/models/user.py")
        assert result["found"] is True
        assert isinstance(result["dependents"], list)

    def test_find_dependents_nonexistent(self, indexed_store: GraphStore):
        result = find_dependents("NonExistent")
        assert result["found"] is False


class TestSearch:
    def test_search_returns_results(self, indexed_store: GraphStore):
        result = search("User")
        assert result["count"] > 0
        assert len(result["results"]) > 0

    def test_search_with_kind_filter(self, indexed_store: GraphStore):
        result = search("User", kind="class")
        for r in result["results"]:
            assert r["kind"] == "class"

    def test_search_no_results(self, indexed_store: GraphStore):
        result = search("xyznonexistent")
        assert result["count"] == 0


class TestGetFileStructure:
    def test_get_file_structure(self, indexed_store: GraphStore):
        result = get_file_structure("src/models/user.py")
        assert result["found"] is True
        assert len(result["nodes"]) > 0
        # Should include file node and at least the User class.
        kinds = {n["kind"] for n in result["nodes"]}
        assert "file" in kinds

    def test_get_file_structure_nonexistent(self, indexed_store: GraphStore):
        result = get_file_structure("nonexistent.py")
        assert result["found"] is False


class TestAnnotationStatus:
    def test_annotation_status(self, indexed_store: GraphStore):
        result = annotation_status()
        assert "error" not in result
        assert "pending" in result
        assert "annotated" in result
        assert "failed" in result
        # After indexing, all nodes should be pending (no auto-annotation).
        assert result["pending"] > 0


class TestGetPendingAnnotations:
    def test_returns_pending_after_indexing(self, indexed_store: GraphStore):
        result = get_pending_annotations(batch_size=5)
        assert "error" not in result
        assert result["count"] > 0
        assert len(result["batch"]) > 0
        assert "taxonomy" in result
        assert isinstance(result["taxonomy"], list)
        # Check first item has expected fields.
        first = result["batch"][0]
        assert "qualified_name" in first
        assert "kind" in first
        assert "source" in first
        assert "neighbors" in first
        assert "recommended_model_tier" in first

    def test_returns_empty_when_no_pending(self, graph_store: GraphStore):
        result = get_pending_annotations()
        assert "error" not in result
        assert result["count"] == 0
        assert result["batch"] == []

    def test_clamps_batch_size(self, graph_store: GraphStore):
        result = get_pending_annotations(batch_size=-1)
        assert "error" not in result


class TestSubmitAnnotations:
    def test_writes_annotations(self, indexed_store: GraphStore):
        # First get pending nodes.
        pending = get_pending_annotations(batch_size=3)
        assert pending["count"] > 0

        # Submit annotations for the first few nodes.
        annotations = [
            {
                "qualified_name": node["qualified_name"],
                "summary": "Test summary",
                "tags": ["utilities", "testing"],
                "role": "Test role",
            }
            for node in pending["batch"][:3]
        ]

        result = submit_annotations(annotations)
        assert "error" not in result
        assert result["written"] > 0
        assert result["failed"] == 0

        # Verify the status changed.
        status = annotation_status()
        assert status["annotated"] > 0

    def test_annotations_surface_in_query_node(self, indexed_store: GraphStore):
        """After submitting annotations, query_node returns tags and role."""
        pending = get_pending_annotations(batch_size=1)
        qname = pending["batch"][0]["qualified_name"]

        submit_annotations(
            [
                {
                    "qualified_name": qname,
                    "summary": "A test node",
                    "tags": ["api", "testing"],
                    "role": "Test handler",
                }
            ]
        )

        result = query_node(qname)
        assert result["found"] is True
        assert result["node"]["tags"] == ["api", "testing"]
        assert result["node"]["role"] == "Test handler"
        assert result["node"]["summary"] == "A test node"

    def test_annotations_surface_in_find_dependents(self, indexed_store: GraphStore):
        """After submitting annotations, find_dependents returns tags, role, summary."""
        # Annotate a node that has dependents.
        pending = get_pending_annotations(batch_size=5)
        for node in pending["batch"]:
            submit_annotations(
                [
                    {
                        "qualified_name": node["qualified_name"],
                        "summary": "Annotated",
                        "tags": ["database"],
                        "role": "Data layer",
                    }
                ]
            )

        result = find_dependents("file::src/models/user.py")
        if result["found"] and result["dependents"]:
            dep = result["dependents"][0]
            assert "tags" in dep
            assert "role" in dep
            assert "summary" in dep

    def test_annotations_surface_in_find_dependencies(self, indexed_store: GraphStore):
        """After submitting annotations, find_dependencies returns tags, role, summary."""
        pending = get_pending_annotations(batch_size=5)
        for node in pending["batch"]:
            submit_annotations(
                [
                    {
                        "qualified_name": node["qualified_name"],
                        "summary": "Annotated",
                        "tags": ["utilities"],
                        "role": "Helper",
                    }
                ]
            )

        result = find_dependencies("file::src/main.py")
        if result["found"] and result["dependencies"]:
            dep = result["dependencies"][0]
            assert "tags" in dep
            assert "role" in dep
            assert "summary" in dep

    def test_annotations_surface_in_search(self, indexed_store: GraphStore):
        """After submitting annotations, search returns tags and role."""
        pending = get_pending_annotations(batch_size=1)
        qname = pending["batch"][0]["qualified_name"]

        submit_annotations(
            [
                {
                    "qualified_name": qname,
                    "summary": "Searchable node",
                    "tags": ["config"],
                    "role": "Configuration",
                }
            ]
        )

        result = search("Searchable")
        assert result["count"] > 0
        found = result["results"][0]
        assert "tags" in found
        assert "role" in found

    def test_annotations_surface_in_get_file_structure(self, indexed_store: GraphStore):
        """After submitting annotations, get_file_structure returns tags and role."""
        pending = get_pending_annotations(batch_size=10)
        for node in pending["batch"]:
            submit_annotations(
                [
                    {
                        "qualified_name": node["qualified_name"],
                        "summary": "Annotated",
                        "tags": ["models"],
                        "role": "Data model",
                    }
                ]
            )

        result = get_file_structure("src/models/user.py")
        assert result["found"] is True
        for node in result["nodes"]:
            assert "tags" in node
            assert "role" in node

    def test_unannotated_nodes_have_empty_tags_and_role(self, indexed_store: GraphStore):
        """Unannotated nodes return tags: [] and role: ''."""
        result = query_node("User")
        assert result["found"] is True
        assert result["node"]["tags"] == []
        assert result["node"]["role"] == ""

    def test_handles_invalid_qualified_name(self, indexed_store: GraphStore):
        annotations = [
            {
                "qualified_name": "nonexistent::Node",
                "summary": "Ghost",
                "tags": [],
                "role": "",
            }
        ]

        result = submit_annotations(annotations)
        assert "error" not in result
        assert result["skipped"] == 1
        assert result["written"] == 0


class TestFindStaleAnnotations:
    def test_no_stale_when_no_annotations(self, indexed_store: GraphStore):
        result = find_stale_annotations()
        assert result["count"] == 0
        assert result["stale_nodes"] == []

    def test_detects_stale_after_content_change(self, indexed_store: GraphStore):
        """Annotate a node, then simulate re-index with changed content_hash."""
        pending = get_pending_annotations(batch_size=1)
        assert pending["count"] > 0
        qname = pending["batch"][0]["qualified_name"]

        submit_annotations(
            [
                {
                    "qualified_name": qname,
                    "summary": "Original summary",
                    "tags": ["test"],
                    "role": "test",
                }
            ]
        )

        # Verify not stale yet.
        result = find_stale_annotations()
        stale_qnames = {n["qualified_name"] for n in result["stale_nodes"]}
        assert qname not in stale_qnames

        # Simulate content change by updating content_hash directly.
        conn = indexed_store._conn  # noqa: SLF001
        conn.execute(
            "UPDATE nodes SET content_hash = 'changed_hash' WHERE qualified_name = ?",
            (qname,),
        )
        conn.commit()

        # Now it should be stale.
        result = find_stale_annotations()
        stale_qnames = {n["qualified_name"] for n in result["stale_nodes"]}
        assert qname in stale_qnames
        stale_node = next(n for n in result["stale_nodes"] if n["qualified_name"] == qname)
        assert stale_node["reason"] == "content_hash_changed"

    def test_pre_migration_node_detected_as_stale(self, indexed_store: GraphStore):
        """Annotated node with NULL annotated_content_hash is stale."""
        conn = indexed_store._conn  # noqa: SLF001
        conn.execute(
            """
            INSERT INTO nodes (kind, name, qualified_name, file_path, start_line, end_line,
                               language, annotation_status, content_hash, annotated_content_hash)
            VALUES ('function', 'old_func', 'mod.old_func', 'old.py', 1, 10,
                    'python', 'annotated', 'abc123', NULL)
            """
        )
        conn.commit()

        result = find_stale_annotations()
        stale_qnames = {n["qualified_name"] for n in result["stale_nodes"]}
        assert "mod.old_func" in stale_qnames

    def test_file_paths_filter(self, indexed_store: GraphStore):
        """file_paths parameter limits scope of stale detection."""
        conn = indexed_store._conn  # noqa: SLF001
        for name, fp in [("f1", "a.py"), ("f2", "b.py")]:
            conn.execute(
                """
                INSERT INTO nodes (kind, name, qualified_name, file_path, start_line, end_line,
                                   language, annotation_status, content_hash, annotated_content_hash)
                VALUES ('function', ?, ?, ?, 1, 10, 'python', 'annotated', 'new_hash', 'old_hash')
                """,
                (name, f"mod.{name}", fp),
            )
        conn.commit()

        result = find_stale_annotations(file_paths=["a.py"])
        stale_qnames = {n["qualified_name"] for n in result["stale_nodes"]}
        assert "mod.f1" in stale_qnames
        assert "mod.f2" not in stale_qnames

    def test_annotation_status_includes_stale_count(self, indexed_store: GraphStore):
        """annotation_status tool returns stale count."""
        result = annotation_status()
        assert "stale" in result
        assert result["stale"] == 0

        conn = indexed_store._conn  # noqa: SLF001
        conn.execute(
            """
            INSERT INTO nodes (kind, name, qualified_name, file_path, start_line, end_line,
                               language, annotation_status, content_hash, annotated_content_hash)
            VALUES ('function', 'stale_fn', 'mod.stale_fn', 'stale.py', 1, 10,
                    'python', 'annotated', 'new', 'old')
            """
        )
        conn.commit()

        result = annotation_status()
        assert result["stale"] == 1


class TestLowQualityAnnotations:
    def test_detects_low_quality_annotations(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "unknown_node",
                    "qualified_name": "mod::unknown_node",
                    "file_path": "mod.py",
                    "start_line": 1,
                    "end_line": 3,
                    "language": "python",
                    "summary": "Code node representing unknown in the system.",
                    "annotation_status": "annotated",
                    "properties": {"role": "Specific role"},
                }
            ]
        )

        result = find_low_quality_annotations()

        assert result["count"] == 1
        assert result["low_quality_nodes"][0]["qualified_name"] == "mod::unknown_node"
        assert "placeholder_phrase" in result["low_quality_nodes"][0]["reasons"]

    def test_requeue_low_quality_annotations_dry_run_default(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "unknown_node",
                    "qualified_name": "mod::unknown_node",
                    "file_path": "mod.py",
                    "start_line": 1,
                    "end_line": 3,
                    "language": "python",
                    "summary": "Code node representing unknown in the system.",
                    "annotation_status": "annotated",
                    "properties": {"role": "Specific role"},
                }
            ]
        )

        result = requeue_low_quality_annotations()

        assert result["dry_run"] is True
        assert result["low_quality"] == 1
        assert result["requeued"] == 0
        node = graph_store.get_node_by_name("mod::unknown_node")
        assert node["annotation_status"] == "annotated"

    def test_requeue_low_quality_annotations_mutates_when_requested(self, graph_store: GraphStore):
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "unknown_node",
                    "qualified_name": "mod::unknown_node",
                    "file_path": "mod.py",
                    "start_line": 1,
                    "end_line": 3,
                    "language": "python",
                    "summary": "Code node representing unknown in the system.",
                    "annotation_status": "annotated",
                    "properties": {"role": "Specific role"},
                }
            ]
        )

        result = requeue_low_quality_annotations(dry_run=False)

        assert result["low_quality"] == 1
        assert result["requeued"] == 1
        node = graph_store.get_node_by_name("mod::unknown_node")
        assert node["annotation_status"] == "pending"


class TestRankNodes:
    def test_rank_by_in_degree(self, indexed_store: GraphStore):
        result = rank_nodes()
        assert "ranked" in result
        assert isinstance(result["ranked"], list)
        # Results should be ordered by score descending.
        scores = [r["score"] for r in result["ranked"]]
        assert scores == sorted(scores, reverse=True)

    def test_rank_returns_degree_fields(self, indexed_store: GraphStore):
        result = rank_nodes()
        if result["ranked"]:
            entry = result["ranked"][0]
            assert "score" in entry
            assert "in_degree" in entry
            assert "out_degree" in entry
            assert "qualified_name" in entry

    def test_rank_kind_filter(self, indexed_store: GraphStore):
        result = rank_nodes(kind="class")
        for entry in result["ranked"]:
            assert entry["kind"] == "class"

    def test_rank_limit(self, indexed_store: GraphStore):
        result = rank_nodes(limit=1)
        assert len(result["ranked"]) <= 1

    def test_rank_scope_file_path(self, indexed_store: GraphStore):
        result = rank_nodes(scope=["src/models/user.py"])
        for entry in result["ranked"]:
            assert entry["file_path"] == "src/models/user.py"

    def test_rank_transitive_algorithm(self, indexed_store: GraphStore):
        result = rank_nodes(algorithm="transitive")
        assert "ranked" in result
        scores = [r["score"] for r in result["ranked"]]
        assert scores == sorted(scores, reverse=True)

    def test_rank_unknown_algorithm(self, indexed_store: GraphStore):
        result = rank_nodes(algorithm="unknown")
        assert "error" in result

    def test_rank_isolated_node_has_zero_score(self, graph_store: GraphStore):
        """A node with no edges should have score 0."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "lonely",
                    "qualified_name": "mod::lonely",
                    "file_path": "src/mod.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                }
            ]
        )
        result = rank_nodes()
        assert len(result["ranked"]) == 1
        assert result["ranked"][0]["score"] == 0
        assert result["ranked"][0]["in_degree"] == 0


class TestGraphDiff:
    def test_graph_diff_before_index_returns_error(self, graph_store: GraphStore):
        """graph_diff before any indexing returns an error."""
        server_main._last_diff = None
        result = graph_diff()
        assert "error" in result

    def test_graph_diff_after_index(self, graph_store: GraphStore):
        """After first index, graph_diff shows all nodes as added."""
        result = index_codebase(full=True)
        assert result["diff_available"] is True
        assert result["diff_summary"]["nodes_added"] > 0

        diff = graph_diff()
        assert "error" not in diff
        assert len(diff["nodes_added"]) > 0
        assert diff["summary"]["nodes_added"] > 0
        # First index: nothing removed or modified.
        assert len(diff["nodes_removed"]) == 0
        assert len(diff["nodes_modified"]) == 0

    def test_graph_diff_incremental_no_changes(self, indexed_store: GraphStore):
        """Incremental re-index with no changes produces empty diff."""
        result = index_codebase(full=False)
        assert result["diff_available"] is True
        assert result["diff_summary"]["nodes_added"] == 0
        assert result["diff_summary"]["nodes_removed"] == 0
        assert result["diff_summary"]["nodes_modified"] == 0

        diff = graph_diff()
        assert "error" not in diff
        assert len(diff["nodes_added"]) == 0
        assert len(diff["nodes_removed"]) == 0
        assert len(diff["nodes_modified"]) == 0

    def test_graph_diff_file_paths_filter(self, graph_store: GraphStore):
        """file_paths filter limits diff to specific files."""
        index_codebase(full=True)
        diff_all = graph_diff()
        diff_filtered = graph_diff(file_paths=["src/models/user.py"])

        # Filtered diff should have <= nodes than full diff.
        assert len(diff_filtered["nodes_added"]) <= len(diff_all["nodes_added"])
        # All nodes in filtered diff should be from the requested file.
        for n in diff_filtered["nodes_added"]:
            assert n["file_path"] == "src/models/user.py"

    def test_graph_diff_include_edges_false(self, graph_store: GraphStore):
        """include_edges=False omits edge-level diff."""
        index_codebase(full=True)
        diff = graph_diff(include_edges=False)
        assert "edges_added" not in diff
        assert "edges_removed" not in diff
        assert "edges_added" not in diff.get("summary", {})

    def test_index_codebase_returns_diff_summary(self, graph_store: GraphStore):
        """index_codebase return includes diff_available and diff_summary."""
        result = index_codebase(full=True)
        assert "diff_available" in result
        assert result["diff_available"] is True
        assert "diff_summary" in result
        assert "nodes_added" in result["diff_summary"]
        assert "nodes_removed" in result["diff_summary"]
        assert "nodes_modified" in result["diff_summary"]


class TestStdioToolDiscovery:
    """Regression test for the module-identity-split bug that caused empty tools/list."""

    def test_tools_list_returns_tools_over_stdio(self):
        """Start the server as a subprocess and verify tools/list returns all 9 tools."""
        handshake = "\n".join(
            [
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"},
                        },
                    }
                ),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            ]
        )

        result = subprocess.run(
            [sys.executable, "-m", "cartograph.server.main"],
            input=handshake,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse each JSON response line.
        responses = [json.loads(line) for line in result.stdout.strip().splitlines()]

        # Find the tools/list response.
        tools_response = next(r for r in responses if r.get("id") == 2)
        tool_names = {t["name"] for t in tools_response["result"]["tools"]}

        expected_tools = {
            "index_codebase",
            "annotation_status",
            "query_node",
            "search",
            "get_file_structure",
            "find_dependencies",
            "find_dependents",
            "get_pending_annotations",
            "submit_annotations",
            "add_litter_box_entry",
            "query_litter_box",
            "add_treat_box_entry",
            "query_treat_box",
            "find_stale_annotations",
            "find_low_quality_annotations",
            "requeue_low_quality_annotations",
            "graph_diff",
            "rank_nodes",
            "batch_query_nodes",
            "get_context_summary",
            "validate_graph",
        }
        assert tool_names == expected_tools


class TestBatchQueryNodes:
    def test_batch_query_found(self, indexed_store: GraphStore):
        result = batch_query_nodes(["User", "UserService"])
        assert result["found"] == 2
        assert result["not_found"] == []
        assert len(result["nodes"]) == 2
        names = {n["name"] for n in result["nodes"]}
        assert "User" in names
        assert "UserService" in names

    def test_batch_query_not_found(self, indexed_store: GraphStore):
        result = batch_query_nodes(["nonexistent_thing"])
        assert result["found"] == 0
        assert result["not_found"] == ["nonexistent_thing"]
        assert result["nodes"] == []

    def test_batch_query_mixed(self, indexed_store: GraphStore):
        result = batch_query_nodes(["User", "nonexistent_thing"])
        assert result["found"] == 1
        assert result["not_found"] == ["nonexistent_thing"]
        assert result["nodes"][0]["name"] == "User"

    def test_batch_query_with_neighbors(self, indexed_store: GraphStore):
        result = batch_query_nodes(["UserService"], include_neighbors=True)
        assert result["found"] == 1
        assert "neighbors" in result["nodes"][0]
        assert isinstance(result["nodes"][0]["neighbors"], list)

    def test_batch_query_without_neighbors(self, indexed_store: GraphStore):
        result = batch_query_nodes(["UserService"], include_neighbors=False)
        assert result["found"] == 1
        assert "neighbors" not in result["nodes"][0]

    def test_batch_query_consistent_with_query_node(self, indexed_store: GraphStore):
        """batch_query_nodes should return the same node data as query_node."""
        single = query_node("User")
        batch = batch_query_nodes(["User"])
        assert single["node"]["qualified_name"] == batch["nodes"][0]["qualified_name"]
        assert single["node"]["kind"] == batch["nodes"][0]["kind"]

    def test_batch_query_by_qualified_name(self, indexed_store: GraphStore):
        result = batch_query_nodes(["models.user::User"])
        assert result["found"] == 1
        assert result["nodes"][0]["qualified_name"] == "models.user::User"


class TestGetContextSummary:
    def test_context_summary_by_file(self, indexed_store: GraphStore):
        result = get_context_summary(file_paths=["src/models/user.py"])
        assert "error" not in result
        assert result["total_nodes"] > 0
        assert "src/models/user.py" in result["groups"]
        for entry in result["groups"]["src/models/user.py"]:
            assert "qualified_name" in entry
            assert "kind" in entry
            assert "in_degree" in entry

    def test_context_summary_with_edges(self, indexed_store: GraphStore):
        result = get_context_summary(file_paths=["src/models/user.py"], include_edges=True)
        assert "edges" in result
        assert isinstance(result["edges"], list)

    def test_context_summary_without_edges(self, indexed_store: GraphStore):
        result = get_context_summary(file_paths=["src/models/user.py"])
        assert "edges" not in result

    def test_context_summary_max_nodes(self, indexed_store: GraphStore):
        result = get_context_summary(max_nodes=2)
        assert result["total_nodes"] <= 2

    def test_context_summary_by_qualified_names(self, indexed_store: GraphStore):
        result = get_context_summary(qualified_names=["models.user::User"])
        assert result["total_nodes"] >= 1
        all_qnames = [
            entry["qualified_name"] for entries in result["groups"].values() for entry in entries
        ]
        assert "models.user::User" in all_qnames

    def test_context_summary_no_filter_returns_nodes(self, indexed_store: GraphStore):
        result = get_context_summary()
        assert result["total_nodes"] > 0


class TestValidateGraph:
    def test_validate_no_store_returns_error(self, graph_store: GraphStore):
        server_main._store = None
        result = validate_graph()
        assert "error" in result
        server_main._store = graph_store

    def test_validate_clean_graph(self, indexed_store: GraphStore):
        result = validate_graph()
        assert "error" not in result
        assert result["summary"]["checks_run"] == 3
        assert result["summary"]["errors"] == 0

    def test_validate_detects_orphan_nodes(self, graph_store: GraphStore):
        """A non-file node with no incoming edges is an orphan."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "orphan_fn",
                    "qualified_name": "mod::orphan_fn",
                    "file_path": "src/mod.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                }
            ]
        )
        result = validate_graph(checks=["orphan_nodes"])
        assert result["passed"] is False
        assert any(i["check"] == "orphan_nodes" for i in result["issues"])
        orphan = next(i for i in result["issues"] if i["check"] == "orphan_nodes")
        assert orphan["node"] == "mod::orphan_fn"
        assert orphan["severity"] == "warning"

    def test_validate_detects_stale_annotations(self, graph_store: GraphStore):
        """Node with changed content_hash after annotation is stale."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "stale_fn",
                    "qualified_name": "mod::stale_fn",
                    "file_path": "src/mod.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                    "annotation_status": "annotated",
                    "content_hash": "new_hash",
                    "annotated_content_hash": "old_hash",
                }
            ]
        )
        result = validate_graph(checks=["stale_annotations"])
        assert result["passed"] is False
        stale = [i for i in result["issues"] if i["check"] == "stale_annotations"]
        assert len(stale) == 1
        assert stale[0]["node"] == "mod::stale_fn"
        assert stale[0]["severity"] == "warning"

    def test_validate_scope_file_path(self, graph_store: GraphStore):
        """Scope limits checks to specific files."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "a",
                    "qualified_name": "a::a",
                    "file_path": "src/a.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                },
                {
                    "kind": "function",
                    "name": "b",
                    "qualified_name": "b::b",
                    "file_path": "src/b.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                },
            ]
        )
        result = validate_graph(scope=["src/a.py"], checks=["orphan_nodes"])
        orphan_nodes = [i["node"] for i in result["issues"] if i["check"] == "orphan_nodes"]
        assert "a::a" in orphan_nodes
        assert "b::b" not in orphan_nodes

    def test_validate_scope_qualified_name(self, graph_store: GraphStore):
        """Scope with qualified names limits checks."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "a",
                    "qualified_name": "mod::a",
                    "file_path": "src/mod.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                    "annotation_status": "annotated",
                    "content_hash": "new",
                    "annotated_content_hash": "old",
                },
                {
                    "kind": "function",
                    "name": "b",
                    "qualified_name": "mod::b",
                    "file_path": "src/mod.py",
                    "start_line": 6,
                    "end_line": 10,
                    "language": "python",
                    "annotation_status": "annotated",
                    "content_hash": "new",
                    "annotated_content_hash": "old",
                },
            ]
        )
        result = validate_graph(scope=["mod::a"], checks=["stale_annotations"])
        stale_nodes = [i["node"] for i in result["issues"]]
        assert "mod::a" in stale_nodes
        assert "mod::b" not in stale_nodes

    def test_validate_checks_filter(self, graph_store: GraphStore):
        """Only requested checks are run."""
        result = validate_graph(checks=["dangling_edges"])
        assert result["summary"]["checks_run"] == 1

    def test_validate_defaults_to_last_diff_scope(self, graph_store: GraphStore):
        """When scope is None and _last_diff exists, use changed files."""
        graph_store.upsert_nodes(
            [
                {
                    "kind": "function",
                    "name": "a",
                    "qualified_name": "a::a",
                    "file_path": "src/a.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                },
                {
                    "kind": "function",
                    "name": "b",
                    "qualified_name": "b::b",
                    "file_path": "src/b.py",
                    "start_line": 1,
                    "end_line": 5,
                    "language": "python",
                },
            ]
        )
        server_main._last_diff = {
            "nodes_added": [{"file_path": "src/a.py", "qualified_name": "a::a"}],
            "nodes_removed": [],
            "nodes_modified": [],
        }
        result = validate_graph(checks=["orphan_nodes"])
        orphan_nodes = [i["node"] for i in result["issues"] if i["check"] == "orphan_nodes"]
        assert "a::a" in orphan_nodes
        assert "b::b" not in orphan_nodes
        server_main._last_diff = None

    def test_validate_return_format(self, graph_store: GraphStore):
        """Return value has the expected structure."""
        result = validate_graph()
        assert "passed" in result
        assert "issues" in result
        assert "summary" in result
        assert "checks_run" in result["summary"]
        assert "errors" in result["summary"]
        assert "warnings" in result["summary"]
        assert "passed" in result["summary"]
