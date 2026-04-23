"""Litter-box and treat-box memory tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import cartograph.server.main as _main
from cartograph.server.main import mcp


@mcp.tool()
def add_litter_box_entry(
    category: str,
    description: str,
    context: str = "",
    source_agent: str = "",
) -> dict[str, Any]:
    """Record a negative lesson in the litter box.

    Use this to remember failures, anti-patterns, unsupported approaches,
    regressions, and things to never do again.

    Args:
        category: One of 'failure', 'anti-pattern', 'unsupported', 'regression', 'never-do'.
        description: What happened or what to avoid.
        context: Optional additional context (file paths, error messages, etc.).
        source_agent: Optional identifier of the agent recording this.

    Returns:
        Dict with the new entry id, box name, and export path.
    """
    store = _main._store
    paths = _main._storage_paths
    if store is None or paths is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import add_entry, export_markdown

    try:
        entry_id = add_entry(store, "litter", category, description, context, source_agent)
    except ValueError as exc:
        return {"error": str(exc)}

    export_path = paths.litter_box_path
    export_markdown(store, "litter", export_path)

    return {"id": entry_id, "box": "litter", "exported_to": str(export_path)}


@mcp.tool()
def query_litter_box(
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Query negative lessons from the litter box.

    Args:
        category: Optional filter — one of 'failure', 'anti-pattern', 'unsupported', 'regression', 'never-do'.
        search: Optional substring to search for in descriptions.
        limit: Maximum number of entries to return (default 50).

    Returns:
        Dict with count and list of matching entries.
    """
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import query_entries

    try:
        entries = query_entries(store, "litter", category=category, search=search, limit=limit)
    except ValueError as exc:
        return {"error": str(exc)}

    return {
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
    }


@mcp.tool()
def add_treat_box_entry(
    category: str,
    description: str,
    context: str = "",
    source_agent: str = "",
) -> dict[str, Any]:
    """Record a positive lesson in the treat box.

    Use this to remember best practices, validated patterns, conventions,
    optimizations, and things to always do.

    Args:
        category: One of 'best-practice', 'validated-pattern', 'always-do', 'convention', 'optimization'.
        description: The positive pattern or practice.
        context: Optional additional context (file paths, examples, etc.).
        source_agent: Optional identifier of the agent recording this.

    Returns:
        Dict with the new entry id, box name, and export path.
    """
    store = _main._store
    paths = _main._storage_paths
    if store is None or paths is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import add_entry, export_markdown

    try:
        entry_id = add_entry(store, "treat", category, description, context, source_agent)
    except ValueError as exc:
        return {"error": str(exc)}

    export_path = paths.treat_box_path
    export_markdown(store, "treat", export_path)

    return {"id": entry_id, "box": "treat", "exported_to": str(export_path)}


@mcp.tool()
def query_treat_box(
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Query positive lessons from the treat box.

    Args:
        category: Optional filter — one of 'best-practice', 'validated-pattern', 'always-do', 'convention', 'optimization'.
        search: Optional substring to search for in descriptions.
        limit: Maximum number of entries to return (default 50).

    Returns:
        Dict with count and list of matching entries.
    """
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import query_entries

    try:
        entries = query_entries(store, "treat", category=category, search=search, limit=limit)
    except ValueError as exc:
        return {"error": str(exc)}

    return {
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
    }
