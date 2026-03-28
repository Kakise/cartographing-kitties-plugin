"""Query and search tools."""

from __future__ import annotations

from typing import Any

import cartograph.server.main as _main
from cartograph.server.main import mcp


@mcp.tool()
def query_node(name: str) -> dict[str, Any]:
    """Find a node by name or qualified name. Returns node details with immediate neighbors."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    # Try exact qualified name match first.
    node = store.get_node_by_name(name)

    # Fall back to partial name match.
    if node is None:
        matches = store.find_nodes(name=name)
        if matches:
            node = matches[0]

    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    # Gather immediate neighbors.
    node_id = node["id"]
    outgoing = store.get_edges(source_id=node_id)
    incoming = store.get_edges(target_id=node_id)

    neighbors: list[dict[str, Any]] = []
    for edge in outgoing:
        target = store.get_node(edge["target_id"])
        if target:
            neighbors.append(
                {
                    "direction": "outgoing",
                    "edge_kind": edge["kind"],
                    "node": _summarise_node(target),
                }
            )
    for edge in incoming:
        source = store.get_node(edge["source_id"])
        if source:
            neighbors.append(
                {
                    "direction": "incoming",
                    "edge_kind": edge["kind"],
                    "node": _summarise_node(source),
                }
            )

    return {
        "found": True,
        "node": _summarise_node(node),
        "neighbors": neighbors,
    }


@mcp.tool()
def search(query: str, kind: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Full-text search across node names and summaries. Returns ranked results."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    results = store.search(query, kind=kind, limit=limit)
    return {
        "count": len(results),
        "results": [_summarise_node(r) for r in results],
    }


@mcp.tool()
def get_file_structure(file_path: str) -> dict[str, Any]:
    """Get all nodes in a given file with their relationships."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    nodes = store.find_nodes(file_path=file_path)
    if not nodes:
        return {"found": False, "message": f"No nodes found for file '{file_path}'"}

    result_nodes: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node["id"]
        outgoing = store.get_edges(source_id=node_id)
        incoming = store.get_edges(target_id=node_id)
        edges = [
            {"direction": "outgoing", "kind": e["kind"], "target_id": e["target_id"]}
            for e in outgoing
        ] + [
            {"direction": "incoming", "kind": e["kind"], "source_id": e["source_id"]}
            for e in incoming
        ]
        result_nodes.append(
            {
                **_summarise_node(node),
                "edges": edges,
            }
        )

    return {"found": True, "file_path": file_path, "nodes": result_nodes}


def _summarise_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a concise representation of a node for tool responses."""
    props = node.get("properties") or {}
    result = {
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
    # Include depth when present (set by transitive traversal queries).
    if "depth" in node:
        result["depth"] = node["depth"]
    return result
