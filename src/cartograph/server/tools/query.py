"""Query and search tools."""

from __future__ import annotations

from typing import Any, cast

from cartograph.server.main import get_store, mcp
from cartograph.server.response_shape import (
    ResponseShape,
    apply_token_budget,
    compact_text,
    cursor_offset,
    paginate_items,
    query_hash,
    validate_response_shape,
)


def node_properties(node: dict[str, Any]) -> dict[str, Any]:
    """Return decoded node properties as a dict."""
    props = node.get("properties")
    return cast(dict[str, Any], props) if isinstance(props, dict) else {}


def _gather_neighbors(
    store: Any,
    node_id: int,
    response_shape: ResponseShape = "standard",
) -> list[dict[str, Any]]:
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
                    "node": summarise_node(target, response_shape=response_shape),
                }
            )
    for edge in incoming:
        source = store.get_node(edge["source_id"])
        if source:
            neighbors.append(
                {
                    "direction": "incoming",
                    "edge_kind": edge["kind"],
                    "node": summarise_node(source, response_shape=response_shape),
                }
            )
    return neighbors


@mcp.tool()
def query_node(
    name: str,
    response_shape: str = "standard",
    token_budget: int | None = None,
) -> dict[str, Any]:
    """Find a node by name or qualified name. Returns node details with immediate neighbors."""
    if error := validate_response_shape(response_shape):
        return error

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

    shape = cast(ResponseShape, response_shape)
    result: dict[str, Any] = {
        "found": True,
        "node": summarise_node(node, response_shape=shape),
    }
    if shape != "compact":
        result["neighbors"] = _gather_neighbors(store, node["id"], response_shape=shape)
    return apply_token_budget(result, token_budget)


@mcp.tool()
def batch_query_nodes(
    names: list[str],
    include_neighbors: bool = True,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Query multiple nodes in one call. Returns found nodes with optional neighbors."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    shape = cast(ResponseShape, response_shape)
    qhash = query_hash(
        "batch_query_nodes",
        {"names": names, "include_neighbors": include_neighbors, "response_shape": response_shape},
    )
    page_names, next_cursor, cursor_error = paginate_items(
        [{"name": name} for name in names],
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error

    found_nodes: list[dict[str, Any]] = []
    not_found: list[str] = []
    for item in page_names:
        name = item["name"]
        node = store.get_node_by_name(name)
        if node is None:
            matches = store.find_nodes(name=name)
            node = matches[0] if matches else None
        if node is None:
            not_found.append(name)
            continue
        result = summarise_node(node, response_shape=shape)
        if include_neighbors and shape != "compact":
            result["neighbors"] = _gather_neighbors(store, node["id"], response_shape=shape)
        found_nodes.append(result)
    return apply_token_budget(
        {
            "found": len(found_nodes),
            "not_found": not_found,
            "nodes": found_nodes,
            "next_cursor": next_cursor,
        },
        token_budget,
    )


@mcp.tool()
def get_context_summary(
    file_paths: list[str] | None = None,
    qualified_names: list[str] | None = None,
    include_edges: bool = False,
    max_nodes: int = 50,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Get a compact grouped summary of nodes, optionally with edges between them."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    shape = cast(ResponseShape, response_shape)
    qhash = query_hash(
        "get_context_summary",
        {
            "file_paths": file_paths,
            "qualified_names": qualified_names,
            "include_edges": include_edges,
            "response_shape": response_shape,
        },
    )
    decoded_page_size = max_nodes
    offset_probe = cursor_offset(cursor) + max_nodes + 1
    rows = store.context_summary(
        file_paths=file_paths, qualified_names=qualified_names, max_nodes=offset_probe
    )
    page_rows, next_cursor, cursor_error = paginate_items(
        rows,
        cursor=cursor,
        page_size=decoded_page_size,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error

    # Group by file_path.
    groups: dict[str, list[dict[str, Any]]] = {}
    node_ids: set[int] = set()
    for row in page_rows:
        props = node_properties(row)
        if shape == "compact":
            entry = summarise_node(row, response_shape="compact")
        else:
            entry = {
                "qualified_name": row["qualified_name"],
                "kind": row["kind"],
                "name": row["name"],
                "role": props.get("role", ""),
                "summary": row.get("summary"),
                "in_degree": row.get("in_degree", 0),
                "centrality": row.get("centrality"),
                "tags": props.get("tags", []),
            }
            if shape == "full":
                entry.update(
                    {
                        "file_path": row.get("file_path"),
                        "start_line": row.get("start_line"),
                        "end_line": row.get("end_line"),
                        "language": row.get("language"),
                    }
                )
        fp = row.get("file_path") or ""
        groups.setdefault(fp, []).append(entry)
        node_ids.add(row["id"])

    result: dict[str, Any] = {
        "total_nodes": len(page_rows),
        "groups": groups,
        "next_cursor": next_cursor,
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

    return apply_token_budget(result, token_budget)


@mcp.tool()
def search(
    query: str,
    kind: str | None = None,
    limit: int = 20,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Full-text search across node names and summaries. Returns ranked results."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    qhash = query_hash("search", {"query": query, "kind": kind, "response_shape": response_shape})
    fetch_limit = max(1, cursor_offset(cursor) + limit + 1)
    results = store.search(query, kind=kind, limit=fetch_limit)
    page, next_cursor, cursor_error = paginate_items(
        results,
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error
    shape = cast(ResponseShape, response_shape)
    return apply_token_budget(
        {
            "count": len(page),
            "results": [summarise_node(r, response_shape=shape) for r in page],
            "next_cursor": next_cursor,
        },
        token_budget,
    )


@mcp.tool()
def get_file_structure(
    file_path: str,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Get all nodes in a given file with their relationships."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    store.ensure_centrality_fresh()

    nodes = store.find_nodes(file_path=file_path)
    if not nodes:
        return {"found": False, "message": f"No nodes found for file '{file_path}'"}

    shape = cast(ResponseShape, response_shape)
    qhash = query_hash(
        "get_file_structure", {"file_path": file_path, "response_shape": response_shape}
    )
    page_nodes, next_cursor, cursor_error = paginate_items(
        nodes,
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error

    result_nodes: list[dict[str, Any]] = []
    for node in page_nodes:
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
        entry = summarise_node(node, response_shape=shape)
        if shape != "compact":
            entry["edges"] = edges
        result_nodes.append(entry)

    return apply_token_budget(
        {"found": True, "file_path": file_path, "nodes": result_nodes, "next_cursor": next_cursor},
        token_budget,
    )


def summarise_node(
    node: dict[str, Any],
    response_shape: ResponseShape = "standard",
) -> dict[str, Any]:
    """Return a concise representation of a node for tool responses."""
    props = node_properties(node)
    if response_shape == "compact":
        result: dict[str, Any] = {
            "qualified_name": node["qualified_name"],
            "kind": node["kind"],
            "role": props.get("role", ""),
            "summary": compact_text(node.get("summary")),
            "centrality": node.get("centrality"),
        }
    else:
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
            "centrality": node.get("centrality"),
        }
    if response_shape == "full":
        result.update(
            {
                "properties": props,
                "content_hash": node.get("content_hash"),
                "annotated_content_hash": node.get("annotated_content_hash"),
                "graph_version": node.get("graph_version"),
                "created_at": node.get("created_at"),
                "updated_at": node.get("updated_at"),
                "in_degree_cache": node.get("in_degree_cache"),
            }
        )
    # Include depth when present (set by transitive traversal queries).
    if "depth" in node:
        result["depth"] = node["depth"]
    return result
