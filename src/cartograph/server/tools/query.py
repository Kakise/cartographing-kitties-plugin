"""Query and search tools."""

from __future__ import annotations

from typing import Any, cast

from cartograph.server.main import get_store, mcp


def node_properties(node: dict[str, Any]) -> dict[str, Any]:
    """Return decoded node properties as a dict."""
    props = node.get("properties")
    return cast(dict[str, Any], props) if isinstance(props, dict) else {}


def _gather_neighbors(store: Any, node_id: int) -> list[dict[str, Any]]:
    """Return immediate neighbor dicts for *node_id*."""
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
                    "node": summarise_node(target),
                }
            )
    for edge in incoming:
        source = store.get_node(edge["source_id"])
        if source:
            neighbors.append(
                {
                    "direction": "incoming",
                    "edge_kind": edge["kind"],
                    "node": summarise_node(source),
                }
            )
    return neighbors


@mcp.tool()
def query_node(name: str) -> dict[str, Any]:
    """Find a node by name or qualified name. Returns node details with immediate neighbors."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    # Try exact qualified name match first.
    node = store.get_node_by_name(name)

    # Fall back to partial name match.
    if node is None:
        matches = store.find_nodes(name=name)
        if matches:
            node = matches[0]

    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    return {
        "found": True,
        "node": summarise_node(node),
        "neighbors": _gather_neighbors(store, node["id"]),
    }


@mcp.tool()
def batch_query_nodes(names: list[str], include_neighbors: bool = True) -> dict[str, Any]:
    """Query multiple nodes in one call. Returns found nodes with optional neighbors."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    found_nodes: list[dict[str, Any]] = []
    not_found: list[str] = []
    for name in names:
        node = store.get_node_by_name(name)
        if node is None:
            matches = store.find_nodes(name=name)
            node = matches[0] if matches else None
        if node is None:
            not_found.append(name)
            continue
        result = summarise_node(node)
        if include_neighbors:
            result["neighbors"] = _gather_neighbors(store, node["id"])
        found_nodes.append(result)
    return {"found": len(found_nodes), "not_found": not_found, "nodes": found_nodes}


@mcp.tool()
def get_context_summary(
    file_paths: list[str] | None = None,
    qualified_names: list[str] | None = None,
    include_edges: bool = False,
    max_nodes: int = 50,
) -> dict[str, Any]:
    """Get a compact grouped summary of nodes, optionally with edges between them."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    rows = store.context_summary(
        file_paths=file_paths, qualified_names=qualified_names, max_nodes=max_nodes
    )

    # Group by file_path.
    groups: dict[str, list[dict[str, Any]]] = {}
    node_ids: set[int] = set()
    for row in rows:
        props = node_properties(row)
        entry: dict[str, Any] = {
            "qualified_name": row["qualified_name"],
            "kind": row["kind"],
            "name": row["name"],
            "role": props.get("role", ""),
            "summary": row.get("summary"),
            "in_degree": row.get("in_degree", 0),
            "centrality": row.get("centrality"),
            "tags": props.get("tags", []),
        }
        fp = row.get("file_path") or ""
        groups.setdefault(fp, []).append(entry)
        node_ids.add(row["id"])

    result: dict[str, Any] = {
        "total_nodes": len(rows),
        "groups": groups,
    }

    if include_edges and node_ids:
        edges: list[dict[str, Any]] = []
        for nid in node_ids:
            for edge in store.get_edges(source_id=nid):
                if edge["target_id"] in node_ids:
                    src = store.get_node(nid)
                    tgt = store.get_node(edge["target_id"])
                    if src and tgt:
                        edges.append(
                            {
                                "from": src["qualified_name"],
                                "to": tgt["qualified_name"],
                                "kind": edge["kind"],
                            }
                        )
        result["edges"] = edges

    return result


@mcp.tool()
def search(query: str, kind: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Full-text search across node names and summaries. Returns ranked results."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    results = store.search(query, kind=kind, limit=limit)
    return {
        "count": len(results),
        "results": [summarise_node(r) for r in results],
    }


@mcp.tool()
def get_file_structure(file_path: str) -> dict[str, Any]:
    """Get all nodes in a given file with their relationships."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

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
                **summarise_node(node),
                "edges": edges,
            }
        )

    return {"found": True, "file_path": file_path, "nodes": result_nodes}


def summarise_node(node: dict[str, Any]) -> dict[str, Any]:
    """Return a concise representation of a node for tool responses."""
    props = node_properties(node)
    result: dict[str, Any] = {
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
        "centrality": node.get("centrality"),
    }
    # Include depth when present (set by transitive traversal queries).
    if "depth" in node:
        result["depth"] = node["depth"]
    return result
