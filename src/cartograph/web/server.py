"""HTTP server for the Cartographing Kittens web graph explorer."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from cartograph.storage import GraphStore


def _safe_int(params: dict[str, list[str]], key: str, default: int) -> int:
    """Parse an integer query parameter, returning *default* on bad input."""
    try:
        return int(params.get(key, [str(default)])[0])
    except (ValueError, IndexError):
        return default


class GraphExplorerHandler(BaseHTTPRequestHandler):
    """Request handler that serves the graph explorer API and frontend."""

    store: ClassVar[GraphStore]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        routes: list[tuple[str, Any]] = [
            (r"^/$", self._serve_frontend),
            (r"^/api/stats$", self._api_stats),
            (r"^/api/nodes$", self._api_nodes),
            (r"^/api/nodes/(\d+)$", self._api_node_detail),
            (r"^/api/edges$", self._api_edges),
            (r"^/api/graph$", self._api_graph),
            (r"^/api/search$", self._api_search),
            (r"^/api/files$", self._api_files),
            (r"^/api/directories$", self._api_directories),
            (r"^/api/tree$", self._api_tree),
        ]

        for pattern, handler in routes:
            match = re.match(pattern, path)
            if match:
                handler(params, *match.groups())
                return

        self._json_response({"error": "Not found"}, status=404)

    def _serve_frontend(self, params: dict[str, list[str]]) -> None:
        from cartograph.web.frontend import FRONTEND_HTML

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(FRONTEND_HTML.encode("utf-8"))

    def _api_stats(self, params: dict[str, list[str]]) -> None:
        store = self.store
        conn = store._conn

        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        edge_count = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        annotated = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE annotation_status = 'annotated'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE annotation_status = 'pending'"
        ).fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE annotation_status = 'failed'"
        ).fetchone()[0]

        kind_counts = {}
        for row in conn.execute(
            "SELECT kind, COUNT(*) as c FROM nodes GROUP BY kind ORDER BY c DESC"
        ):
            kind_counts[row[0]] = row[1]

        self._json_response(
            {
                "nodes": node_count,
                "edges": edge_count,
                "annotated": annotated,
                "pending": pending,
                "failed": failed,
                "kinds": kind_counts,
            }
        )

    def _api_nodes(self, params: dict[str, list[str]]) -> None:
        store = self.store
        kind = params.get("kind", [None])[0]
        limit = min(_safe_int(params, "limit", 50), 500)
        offset = _safe_int(params, "offset", 0)

        query = "SELECT * FROM nodes"
        args: list[Any] = []
        if kind:
            query += " WHERE kind = ?"
            args.append(kind)
        query += " ORDER BY file_path, start_line LIMIT ? OFFSET ?"
        args.extend([limit, offset])

        rows = store._conn.execute(query, args).fetchall()
        nodes = [self._node_to_dict(row) for row in rows]
        self._json_response({"count": len(nodes), "nodes": nodes})

    def _api_node_detail(self, params: dict[str, list[str]], node_id: str) -> None:
        store = self.store
        node = store.get_node(int(node_id))
        if node is None:
            self._json_response({"error": "Node not found"}, status=404)
            return

        outgoing = store.get_edges(source_id=int(node_id))
        incoming = store.get_edges(target_id=int(node_id))

        neighbors = []
        for edge in outgoing:
            target = store.get_node(edge["target_id"])
            if target:
                neighbors.append(
                    {
                        "direction": "outgoing",
                        "edge_kind": edge["kind"],
                        "node": self._node_to_dict_from_store(target),
                    }
                )
        for edge in incoming:
            source = store.get_node(edge["source_id"])
            if source:
                neighbors.append(
                    {
                        "direction": "incoming",
                        "edge_kind": edge["kind"],
                        "node": self._node_to_dict_from_store(source),
                    }
                )

        self._json_response(
            {
                "node": self._node_to_dict_from_store(node),
                "neighbors": neighbors,
            }
        )

    def _api_edges(self, params: dict[str, list[str]]) -> None:
        store = self.store
        source_id = params.get("source_id", [None])[0]
        target_id = params.get("target_id", [None])[0]
        kind = params.get("kind", [None])[0]

        kwargs: dict[str, Any] = {}
        if source_id:
            try:
                kwargs["source_id"] = int(source_id)
            except ValueError:
                pass
        if target_id:
            try:
                kwargs["target_id"] = int(target_id)
            except ValueError:
                pass
        if kind:
            kwargs["kind"] = kind

        edges = store.get_edges(**kwargs) if kwargs else []
        self._json_response(
            {
                "count": len(edges),
                "edges": [dict(e) for e in edges],
            }
        )

    def _api_graph(self, params: dict[str, list[str]]) -> None:
        store = self.store
        conn = store._conn
        full = params.get("full", [None])[0] == "true"
        limit = 10000 if full else min(_safe_int(params, "limit", 300), 500)
        directory = params.get("directory", [None])[0]
        file_path = params.get("file_path", [None])[0]

        if file_path:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE file_path = ? "
                "AND kind != 'file' ORDER BY start_line LIMIT ?",
                [file_path, limit],
            ).fetchall()
        elif directory:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE file_path LIKE ? "
                "AND kind != 'file' ORDER BY file_path, start_line LIMIT ?",
                [directory + "/%", limit],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM nodes ORDER BY file_path, start_line LIMIT ?", [limit]
            ).fetchall()

        nodes = [self._node_to_dict(row) for row in rows]

        node_ids = {node["id"] for node in nodes}
        edges: list[dict[str, Any]] = []
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            edge_rows = conn.execute(
                f"SELECT * FROM edges WHERE source_id IN ({placeholders}) "  # noqa: S608
                f"AND target_id IN ({placeholders})",
                [*node_ids, *node_ids],
            ).fetchall()
            edges = [
                {
                    "id": row["id"],
                    "source_id": row["source_id"],
                    "target_id": row["target_id"],
                    "kind": row["kind"],
                    "weight": row["weight"],
                }
                for row in edge_rows
            ]

        self._json_response({"nodes": nodes, "edges": edges})

    def _api_search(self, params: dict[str, list[str]]) -> None:
        store = self.store
        query = params.get("q", [""])[0]
        if not query:
            self._json_response({"count": 0, "results": []})
            return

        kind = params.get("kind", [None])[0]
        limit = min(_safe_int(params, "limit", 20), 100)

        results = store.search(query, kind=kind, limit=limit)
        self._json_response(
            {
                "count": len(results),
                "results": [self._node_to_dict_from_store(r) for r in results],
            }
        )

    def _api_directories(self, params: dict[str, list[str]]) -> None:
        """Return directory-level aggregation for the overview treemap."""
        conn = self.store._conn

        # Group files by directory, count nodes per directory
        rows = conn.execute(
            "SELECT file_path, kind, COUNT(*) as cnt FROM nodes "
            "WHERE kind != 'file' AND file_path IS NOT NULL "
            "GROUP BY file_path, kind"
        ).fetchall()

        dirs: dict[str, dict[str, Any]] = {}
        for row in rows:
            fp = row[0]
            parts = fp.split("/")
            dir_path = "/".join(parts[:-1]) if len(parts) > 1 else "(root)"
            if dir_path not in dirs:
                dirs[dir_path] = {
                    "path": dir_path,
                    "node_count": 0,
                    "file_count": 0,
                    "files": set(),
                    "kinds": {},
                }
            dirs[dir_path]["node_count"] += row[2]
            dirs[dir_path]["files"].add(fp)
            kind = row[1]
            dirs[dir_path]["kinds"][kind] = dirs[dir_path]["kinds"].get(kind, 0) + row[2]

        result = []
        for d in sorted(dirs.values(), key=lambda x: x["path"]):
            d["file_count"] = len(d["files"])
            del d["files"]
            result.append(d)

        self._json_response({"directories": result})

    def _api_tree(self, params: dict[str, list[str]]) -> None:
        """Return recursive directory tree with node counts at each level."""
        conn = self.store._conn
        rows = conn.execute(
            "SELECT file_path, COUNT(*) as cnt FROM nodes "
            "WHERE kind != 'file' AND file_path IS NOT NULL "
            "GROUP BY file_path"
        ).fetchall()

        def _make_node(name: str, node_type: str, node_count: int = 0) -> dict[str, Any]:
            return {
                "name": name,
                "type": node_type,
                "node_count": node_count,
                "children": list[dict[str, Any]](),
            }

        root = _make_node("(root)", "directory")

        for row in rows:
            file_path: str = row[0]
            count: int = row[1]
            parts = file_path.split("/")

            current = root
            # Walk/create directory path
            for part in parts[:-1]:
                children: list[dict[str, Any]] = current["children"]
                child: dict[str, Any] | None = None
                for c in children:
                    if c["name"] == part and c["type"] == "directory":
                        child = c
                        break
                if child is None:
                    child = _make_node(part, "directory")
                    children.append(child)
                current = child

            # Add file leaf
            children_list: list[dict[str, Any]] = current["children"]
            children_list.append(_make_node(parts[-1], "file", count))

        # Recursively sum node_count
        def _sum_counts(node: dict[str, Any]) -> int:
            if node["type"] == "file":
                return int(node["node_count"])
            children_inner: list[dict[str, Any]] = node["children"]
            total = sum(_sum_counts(c) for c in children_inner)
            node["node_count"] = total
            return total

        _sum_counts(root)

        # Sort children alphabetically at each level
        def _sort_tree(node: dict[str, Any]) -> None:
            children_sort: list[dict[str, Any]] = node["children"]
            children_sort.sort(key=lambda c: (0 if c["type"] == "directory" else 1, c["name"]))
            for c in children_sort:
                _sort_tree(c)

        _sort_tree(root)

        self._json_response({"tree": root})

    def _api_files(self, params: dict[str, list[str]]) -> None:
        conn = self.store._conn
        rows = conn.execute(
            "SELECT file_path, COUNT(*) as node_count FROM nodes "
            "WHERE kind != 'file' GROUP BY file_path ORDER BY file_path"
        ).fetchall()
        self._json_response(
            {"files": [{"file_path": row[0], "node_count": row[1]} for row in rows]}
        )

    def _json_response(self, data: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _node_to_dict(self, row: Any) -> dict[str, Any]:
        """Convert a raw sqlite3.Row to a node dict with annotation fields."""
        d = dict(row)
        props = d.pop("properties", None) or "{}"
        if isinstance(props, str):
            import json as _json

            props = _json.loads(props) if props else {}
        d["tags"] = props.get("tags", [])
        d["role"] = props.get("role", "")
        return d

    def _node_to_dict_from_store(self, node: dict[str, Any]) -> dict[str, Any]:
        """Convert a GraphStore dict (already deserialized) to API response format."""
        props = node.get("properties") or {}
        return {
            "id": node["id"],
            "kind": node["kind"],
            "name": node["name"],
            "qualified_name": node["qualified_name"],
            "file_path": node.get("file_path"),
            "start_line": node.get("start_line"),
            "end_line": node.get("end_line"),
            "language": node.get("language"),
            "summary": node.get("summary"),
            "annotation_status": node.get("annotation_status"),
            "tags": props.get("tags", []),
            "role": props.get("role", ""),
        }

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging."""


def make_handler_class(store: GraphStore) -> type[GraphExplorerHandler]:
    """Create a handler class with the store bound as a class attribute."""

    class BoundHandler(GraphExplorerHandler):
        pass

    BoundHandler.store = store  # type: ignore[attr-defined]
    return BoundHandler


def run_server(store: GraphStore, port: int = 3333) -> None:
    """Start the graph explorer HTTP server."""
    handler_class = make_handler_class(store)

    server = HTTPServer(("127.0.0.1", port), handler_class)
    print(f"Cartographing Kittens running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()
