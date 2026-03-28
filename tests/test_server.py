"""Tests for the Cartograph MCP server tools."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# The tool modules read state from cartograph.server.main module-level vars.
import cartograph.server.main as server_main
from cartograph.indexing import Indexer
from cartograph.server.tools.analysis import find_dependencies, find_dependents
from cartograph.server.tools.annotate import get_pending_annotations, submit_annotations
from cartograph.server.tools.index import annotation_status, index_codebase
from cartograph.server.tools.query import get_file_structure, query_node, search
from cartograph.storage import GraphStore, create_connection

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"


@pytest.fixture()
def graph_store(tmp_path: Path):
    """Create a GraphStore backed by a temp database and wire it into server state."""
    db_path = tmp_path / "graph.db"
    conn = create_connection(db_path)
    store = GraphStore(conn)

    # Wire module-level state so tools can find it.
    server_main._store = store
    server_main._root = FIXTURE_DIR.resolve()

    yield store

    store.close()
    server_main._store = None
    server_main._root = None


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
            [{"qualified_name": qname, "summary": "A test node", "tags": ["api", "testing"], "role": "Test handler"}]
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
                [{"qualified_name": node["qualified_name"], "summary": "Annotated", "tags": ["database"], "role": "Data layer"}]
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
                [{"qualified_name": node["qualified_name"], "summary": "Annotated", "tags": ["utilities"], "role": "Helper"}]
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
            [{"qualified_name": qname, "summary": "Searchable node", "tags": ["config"], "role": "Configuration"}]
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
                [{"qualified_name": node["qualified_name"], "summary": "Annotated", "tags": ["models"], "role": "Data model"}]
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
        }
        assert tool_names == expected_tools
