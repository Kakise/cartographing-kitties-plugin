"""Dependency and impact analysis tools."""

from __future__ import annotations

from typing import Any

import cartograph.server.main as _main
from cartograph.server.main import mcp
from cartograph.server.tools.query import _summarise_node


def _resolve_node(name: str) -> dict[str, Any] | None:
    """Look up a node by qualified name, falling back to name match."""
    store = _main._store
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
) -> dict[str, Any]:
    """Find transitive dependencies of a node. Returns nodes this depends on."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    node = _resolve_node(name)
    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    deps = store.transitive_dependencies(node["id"], edge_kinds=edge_kinds, max_depth=max_depth)

    return {
        "found": True,
        "source": {"id": node["id"], "qualified_name": node["qualified_name"]},
        "count": len(deps),
        "dependencies": [_summarise_node(d) for d in deps],
    }


@mcp.tool()
def find_dependents(
    name: str,
    edge_kinds: list[str] | None = None,
    max_depth: int = 5,
) -> dict[str, Any]:
    """Find what depends on a node (impact analysis). Returns nodes that depend on this."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    node = _resolve_node(name)
    if node is None:
        return {"found": False, "message": f"No node found matching '{name}'"}

    deps = store.reverse_dependencies(node["id"], edge_kinds=edge_kinds, max_depth=max_depth)

    return {
        "found": True,
        "target": {"id": node["id"], "qualified_name": node["qualified_name"]},
        "count": len(deps),
        "dependents": [_summarise_node(d) for d in deps],
    }
