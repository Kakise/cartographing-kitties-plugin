"""Litter-box and treat-box memory tools."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from cartograph.server.main import get_context, get_store, mcp


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
    runtime_context = get_context()
    if runtime_context is None:
        return {"error": "Server not initialised"}
    store = runtime_context.store
    paths = runtime_context.storage_paths

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
    token_budget: int | None = None,
) -> dict[str, Any]:
    """Query negative lessons from the litter box.

    Args:
        category: Optional filter — one of 'failure', 'anti-pattern', 'unsupported', 'regression', 'never-do'.
        search: Optional substring to search for in descriptions.
        limit: Maximum number of entries to return (default 50).
        token_budget: Optional approximate token budget (len/4). When set the result
            is re-ranked by ``relevance_score`` and truncated to fit; ``truncated``
            in the response is True when entries were dropped to honor the budget.

    Returns:
        Dict with count, list of matching entries (each carrying ``relevance_score``),
        and a ``truncated`` flag indicating whether the budget caused truncation.
    """
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import query_entries

    try:
        all_entries = query_entries(store, "litter", category=category, search=search, limit=limit)
        entries = (
            query_entries(
                store,
                "litter",
                category=category,
                search=search,
                limit=limit,
                token_budget=token_budget,
            )
            if token_budget is not None
            else all_entries
        )
    except ValueError as exc:
        return {"error": str(exc)}

    return {
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
        "truncated": token_budget is not None and len(entries) < len(all_entries),
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
    runtime_context = get_context()
    if runtime_context is None:
        return {"error": "Server not initialised"}
    store = runtime_context.store
    paths = runtime_context.storage_paths

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
    token_budget: int | None = None,
) -> dict[str, Any]:
    """Query positive lessons from the treat box.

    Args:
        category: Optional filter — one of 'best-practice', 'validated-pattern', 'always-do', 'convention', 'optimization'.
        search: Optional substring to search for in descriptions.
        limit: Maximum number of entries to return (default 50).
        token_budget: Optional approximate token budget (len/4). See ``query_litter_box``.

    Returns:
        Dict with count, list of matching entries (each carrying ``relevance_score``),
        and a ``truncated`` flag indicating whether the budget caused truncation.
    """
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import query_entries

    try:
        all_entries = query_entries(store, "treat", category=category, search=search, limit=limit)
        entries = (
            query_entries(
                store,
                "treat",
                category=category,
                search=search,
                limit=limit,
                token_budget=token_budget,
            )
            if token_budget is not None
            else all_entries
        )
    except ValueError as exc:
        return {"error": str(exc)}

    return {
        "count": len(entries),
        "entries": [asdict(e) for e in entries],
        "truncated": token_budget is not None and len(entries) < len(all_entries),
    }


@mcp.tool()
def get_agent_handoff(run_id: str) -> dict[str, Any]:
    """Fetch a persisted agent-handoff payload by its ``run_id``.

    Skills stage agent run results via the unified output contract; the
    orchestrator carries only the ``run_id`` through the conversation and pulls
    the full payload here at synthesis time. Expired records (TTL elapsed) are
    treated as missing.

    Args:
        run_id: The handle returned by ``stage_handoff``.

    Returns:
        Dict with the handoff record fields, or ``{"error": ...}`` when the
        run_id is unknown or expired.
    """

    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.memory import get_handoff

    record = get_handoff(store, run_id)
    if record is None:
        return {"error": f"unknown or expired run_id: {run_id}"}

    return {
        "run_id": record.run_id,
        "session_id": record.session_id,
        "agent_name": record.agent_name,
        "role": record.role,
        "payload": record.payload,
        "created_at": record.created_at,
        "expires_at": record.expires_at,
    }
