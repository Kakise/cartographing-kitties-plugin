from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import cartograph.server.main as server_main
from cartograph.compat import StoragePaths
from cartograph.indexing import Indexer
from cartograph.server.main import mcp
from cartograph.server.response_shape import estimate_tokens
from cartograph.server.tools.analysis import find_dependents, rank_nodes
from cartograph.server.tools.index import annotation_status, index_codebase
from cartograph.server.tools.query import get_file_structure, query_node, search
from cartograph.server.tools.reactive import validate_graph
from cartograph.storage import GraphStore, create_connection

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"


@pytest.fixture()
def indexed_store(tmp_path: Path):
    data_dir = tmp_path / ".pawprints"
    data_dir.mkdir()
    db_path = data_dir / "graph.db"
    conn = create_connection(db_path)
    store = GraphStore(conn)

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
    Indexer(FIXTURE_DIR, store).index_all()

    yield store

    store.close()
    server_main._store = None
    server_main._root = None
    server_main._storage_paths = None
    server_main._last_diff = None


def test_query_node_compact_omits_neighbors(indexed_store: GraphStore) -> None:
    result = query_node("UserService", response_shape="compact")

    assert result["found"] is True
    assert "neighbors" not in result
    assert set(result["node"]) == {"qualified_name", "kind", "role", "summary", "centrality"}
    assert estimate_tokens(result) <= 2000


def test_unknown_response_shape_returns_structured_error(indexed_store: GraphStore) -> None:
    result = query_node("User", response_shape="bogus")

    assert result == {
        "error": "unknown response_shape 'bogus'. Use 'compact', 'standard', or 'full'."
    }


def test_search_cursor_paginates_results(indexed_store: GraphStore) -> None:
    first = search("User", limit=1, response_shape="compact")
    assert first["count"] == 1
    assert first["next_cursor"] is not None

    second = search("User", limit=1, response_shape="compact", cursor=first["next_cursor"])
    combined = [first["results"][0]["qualified_name"], second["results"][0]["qualified_name"]]

    full = search("User", limit=2, response_shape="compact")
    assert combined == [item["qualified_name"] for item in full["results"]]


def test_malformed_cursor_returns_structured_error(indexed_store: GraphStore) -> None:
    result = search("User", cursor="not-a-cursor")

    assert result["error"] == "invalid_cursor"


def test_token_budget_truncates_high_traffic_tool(indexed_store: GraphStore) -> None:
    result = find_dependents("file::src/models/user.py", max_depth=5, token_budget=160)

    assert estimate_tokens(result) <= 160
    assert result["truncated_items"] > 0
    assert result["budget_used"] <= 160
    assert result["budget_remaining"] >= 0


def test_get_file_structure_accepts_response_shape_and_budget(
    indexed_store: GraphStore,
) -> None:
    result = get_file_structure("src/models/user.py", response_shape="compact", token_budget=200)

    assert result["found"] is True
    assert estimate_tokens(result) <= 200
    assert "edges" not in result["nodes"][0]


def test_rank_nodes_cursor_returns_next_page(indexed_store: GraphStore) -> None:
    first = rank_nodes(limit=1, response_shape="compact")
    assert first["next_cursor"] is not None

    second = rank_nodes(limit=1, response_shape="compact", cursor=first["next_cursor"])
    assert second["ranked"]
    assert first["ranked"][0]["qualified_name"] != second["ranked"][0]["qualified_name"]


def test_cleanable_hints_on_incidental_tools(indexed_store: GraphStore) -> None:
    index_result = index_codebase(full=False)
    status = annotation_status()
    validation = validate_graph()

    assert index_result["cleanable"] is True
    assert status["cleanable"] is True
    assert validation["passed"] is True
    assert validation["cleanable"] is True


def test_registered_tools_expose_input_and_output_schemas() -> None:
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    for name in [
        "query_node",
        "batch_query_nodes",
        "search",
        "get_file_structure",
        "get_context_summary",
        "find_dependencies",
        "find_dependents",
        "rank_nodes",
    ]:
        tool = tools[name]
        assert tool.outputSchema
        input_properties = tool.inputSchema["properties"]
        assert "response_shape" in input_properties
        assert "token_budget" in input_properties
