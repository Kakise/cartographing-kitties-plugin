"""Dependency and impact analysis tools."""

from __future__ import annotations

from typing import Any, cast

from cartograph.server.main import get_store, mcp
from cartograph.server.response_shape import (
    ResponseShape,
    apply_token_budget,
    cursor_offset,
    paginate_items,
    query_hash,
    validate_response_shape,
)
from cartograph.server.tools.query import summarise_node


def _resolve_node(name: str) -> dict[str, Any] | None:
    """Look up a node by qualified name, falling back to name match."""
    store = get_store()
    if store is None:
        return None
    node = store.get_node_by_name(name)
    if node is None:
        matches = store.find_nodes(name=name)
        if matches:
            node = matches[0]
    return node


@mcp.tool()
def find_dependencies(
    name: str,
    edge_kinds: list[str] | None = None,
    max_depth: int = 5,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Find transitive dependencies of a node. Returns nodes this depends on."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    node = _resolve_node(name)
    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    deps = store.transitive_dependencies(node["id"], edge_kinds=edge_kinds, max_depth=max_depth)
    qhash = query_hash(
        "find_dependencies",
        {
            "name": name,
            "edge_kinds": edge_kinds,
            "max_depth": max_depth,
            "response_shape": response_shape,
        },
    )
    page, next_cursor, cursor_error = paginate_items(
        deps,
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error
    shape = cast(ResponseShape, response_shape)

    return apply_token_budget(
        {
            "found": True,
            "source": {"id": node["id"], "qualified_name": node["qualified_name"]},
            "count": len(page),
            "dependencies": [summarise_node(d, response_shape=shape) for d in page],
            "next_cursor": next_cursor,
        },
        token_budget,
    )


@mcp.tool()
def find_dependents(
    name: str,
    edge_kinds: list[str] | None = None,
    max_depth: int = 5,
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Find what depends on a node (impact analysis). Returns nodes that depend on this."""
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    node = _resolve_node(name)
    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    deps = store.reverse_dependencies(node["id"], edge_kinds=edge_kinds, max_depth=max_depth)
    qhash = query_hash(
        "find_dependents",
        {
            "name": name,
            "edge_kinds": edge_kinds,
            "max_depth": max_depth,
            "response_shape": response_shape,
        },
    )
    page, next_cursor, cursor_error = paginate_items(
        deps,
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error
    shape = cast(ResponseShape, response_shape)

    return apply_token_budget(
        {
            "found": True,
            "target": {"id": node["id"], "qualified_name": node["qualified_name"]},
            "count": len(page),
            "dependents": [summarise_node(d, response_shape=shape) for d in page],
            "next_cursor": next_cursor,
        },
        token_budget,
    )


def _is_file_path(entry: str) -> bool:
    """Heuristic: treat scope entries containing / or common extensions as file paths."""
    return "/" in entry or entry.endswith((".py", ".ts", ".js"))


@mcp.tool()
def rank_nodes(
    scope: list[str] | None = None,
    kind: str | None = None,
    limit: int = 20,
    algorithm: str = "in_degree",
    response_shape: str = "standard",
    token_budget: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Rank nodes by importance (in-degree or transitive dependents).

    Parameters
    ----------
    scope : list[str] | None
        Optional list of file paths or qualified names to restrict the ranking.
    kind : str | None
        Filter to a specific node kind (e.g. "class", "function").
    limit : int
        Maximum number of results to return.
    algorithm : str
        "in_degree" (default) for direct edge count, or "transitive" for
        recursive reverse-dependency count.
    """
    if error := validate_response_shape(response_shape):
        return error

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    if algorithm not in ("in_degree", "transitive"):
        return {"error": f"Unknown algorithm '{algorithm}'. Use 'in_degree' or 'transitive'."}

    # Partition scope entries into file paths vs qualified names.
    scope_file_paths: list[str] | None = None
    scope_qnames: list[str] | None = None
    if scope:
        fps = [s for s in scope if _is_file_path(s)]
        qns = [s for s in scope if not _is_file_path(s)]
        scope_file_paths = fps or None
        scope_qnames = qns or None

    fetch_limit = cursor_offset(cursor) + limit + 1
    results: list[dict[str, Any]] = []
    if algorithm == "in_degree":
        ranked = store.rank_by_in_degree(
            scope_file_paths=scope_file_paths,
            scope_qnames=scope_qnames,
            kind=kind,
            limit=fetch_limit,
        )
        for node in ranked:
            entry = summarise_node(node, response_shape=cast(ResponseShape, response_shape))
            entry["in_degree"] = node.get("in_degree", 0)
            entry["out_degree"] = node.get("out_degree", 0)
            entry["score"] = node.get("in_degree", 0)
            results.append(entry)
    else:
        ranked = store.rank_by_transitive(
            scope_qnames=scope_qnames,
            limit=fetch_limit,
        )
        for node in ranked:
            entry = summarise_node(node, response_shape=cast(ResponseShape, response_shape))
            entry["in_degree"] = node.get("in_degree", 0)
            entry["out_degree"] = node.get("out_degree", 0)
            entry["score"] = node.get("transitive_count", 0)
            results.append(entry)

    qhash = query_hash(
        "rank_nodes",
        {
            "scope": scope,
            "kind": kind,
            "algorithm": algorithm,
            "response_shape": response_shape,
        },
    )
    page, next_cursor, cursor_error = paginate_items(
        results,
        cursor=cursor,
        page_size=limit,
        query_hash_value=qhash,
    )
    if cursor_error is not None:
        return cursor_error

    return apply_token_budget({"ranked": page, "next_cursor": next_cursor}, token_budget)
