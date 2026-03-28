"""Tests for the Cartograph web graph explorer."""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import pytest

# We need to wire server_main state for annotation tools.
import cartograph.server.main as server_main
from cartograph.indexing import Indexer
from cartograph.server.tools.annotate import get_pending_annotations, submit_annotations
from cartograph.storage import GraphStore

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"


@pytest.fixture()
def store(tmp_path: Path):
    import sqlite3 as _sqlite3

    from cartograph.storage.schema import SCHEMA_SQL

    db_path = tmp_path / "graph.db"
    conn = _sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    gs = GraphStore(conn)
    yield gs
    gs.close()


@pytest.fixture()
def indexed_store(store: GraphStore):
    indexer = Indexer(FIXTURE_DIR, store)
    indexer.index_all()
    return store


@pytest.fixture()
def annotated_store(indexed_store: GraphStore):
    """Index and annotate a few nodes so annotation fields are populated."""
    # Wire module-level state for annotation tools.
    server_main._store = indexed_store
    server_main._root = FIXTURE_DIR.resolve()

    pending = get_pending_annotations(batch_size=5)
    annotations = [
        {
            "qualified_name": node["qualified_name"],
            "summary": f"Summary for {node['name']}",
            "tags": ["test-tag"],
            "role": "Test role",
        }
        for node in pending["batch"]
    ]
    submit_annotations(annotations)

    server_main._store = None
    server_main._root = None
    return indexed_store


@pytest.fixture()
def server_url(indexed_store: GraphStore):
    """Start the server in a background thread, yield the base URL, then shut down."""
    from http.server import HTTPServer

    from cartograph.web.server import make_handler_class

    handler_class = make_handler_class(indexed_store)
    httpd = HTTPServer(("127.0.0.1", 0), handler_class)
    port = httpd.server_address[1]

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    # Wait for server to be ready.
    time.sleep(0.1)

    yield f"127.0.0.1:{port}"

    httpd.shutdown()


def get(url: str, path: str) -> tuple[int, dict]:
    conn = HTTPConnection(url)
    conn.request("GET", path)
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    if resp.headers.get("Content-Type", "").startswith("application/json"):
        return resp.status, json.loads(body)
    return resp.status, {"_html": body}


class TestFrontend:
    def test_serves_html(self, server_url: str):
        status, data = get(server_url, "/")
        assert status == 200
        assert "Cartograph" in data["_html"]


class TestApiStats:
    def test_returns_stats(self, server_url: str):
        status, data = get(server_url, "/api/stats")
        assert status == 200
        assert data["nodes"] > 0
        assert data["edges"] > 0
        assert "kinds" in data
        assert "annotated" in data
        assert "pending" in data


class TestApiNodes:
    def test_lists_nodes(self, server_url: str):
        status, data = get(server_url, "/api/nodes")
        assert status == 200
        assert data["count"] > 0
        node = data["nodes"][0]
        assert "id" in node
        assert "kind" in node
        assert "name" in node
        assert "tags" in node
        assert "role" in node

    def test_filter_by_kind(self, server_url: str):
        status, data = get(server_url, "/api/nodes?kind=class")
        assert status == 200
        for node in data["nodes"]:
            assert node["kind"] == "class"

    def test_pagination(self, server_url: str):
        status, data = get(server_url, "/api/nodes?limit=2&offset=0")
        assert status == 200
        assert data["count"] <= 2


class TestApiNodeDetail:
    def test_returns_node_with_neighbors(self, server_url: str):
        # First get a node id.
        _, nodes_data = get(server_url, "/api/nodes?limit=1")
        node_id = nodes_data["nodes"][0]["id"]

        status, data = get(server_url, f"/api/nodes/{node_id}")
        assert status == 200
        assert "node" in data
        assert "neighbors" in data
        assert data["node"]["id"] == node_id

    def test_not_found(self, server_url: str):
        status, data = get(server_url, "/api/nodes/999999")
        assert status == 404


class TestApiSearch:
    def test_search(self, server_url: str):
        status, data = get(server_url, "/api/search?q=User")
        assert status == 200
        assert data["count"] > 0
        assert "tags" in data["results"][0]
        assert "role" in data["results"][0]

    def test_empty_search(self, server_url: str):
        status, data = get(server_url, "/api/search?q=")
        assert status == 200
        assert data["count"] == 0


class TestApiEdges:
    def test_returns_edges(self, server_url: str):
        # Get a node with edges first.
        _, nodes_data = get(server_url, "/api/nodes?limit=1")
        node_id = nodes_data["nodes"][0]["id"]

        status, data = get(server_url, f"/api/edges?source_id={node_id}")
        assert status == 200
        assert "edges" in data


class TestApiFiles:
    def test_returns_files(self, server_url: str):
        status, data = get(server_url, "/api/files")
        assert status == 200
        assert len(data["files"]) > 0
        assert "file_path" in data["files"][0]
        assert "node_count" in data["files"][0]


class TestAnnotatedNodes:
    def test_annotations_in_api_response(self, annotated_store: GraphStore):
        """Verify annotation data flows through the web API."""
        from http.server import HTTPServer

        from cartograph.web.server import make_handler_class

        handler_class = make_handler_class(annotated_store)
        httpd = HTTPServer(("127.0.0.1", 0), handler_class)
        port = httpd.server_address[1]

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.1)

        url = f"127.0.0.1:{port}"

        # Search for annotated nodes.
        status, data = get(url, "/api/search?q=Summary")
        assert status == 200
        if data["count"] > 0:
            result = data["results"][0]
            assert result["tags"] == ["test-tag"]
            assert result["role"] == "Test role"

        httpd.shutdown()
