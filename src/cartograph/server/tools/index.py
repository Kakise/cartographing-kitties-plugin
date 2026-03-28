"""Indexing and annotation status tools."""

from __future__ import annotations

from typing import Any

import cartograph.server.main as _main
from cartograph.server.main import mcp


@mcp.tool()
def index_codebase(full: bool = False) -> dict[str, Any]:
    """Trigger structural indexing of the codebase.

    Args:
        full: If True, re-index all files. If False (default), only index changed files.

    Returns stats about files parsed, nodes created, edges created.
    """
    store = _main._store
    root = _main._root
    if store is None or root is None:
        return {"error": "Server not initialised"}

    from cartograph.indexing import Indexer

    indexer = Indexer(root, store)
    stats = indexer.index_all() if full else indexer.index_changed()

    return {
        "files_parsed": stats.files_parsed,
        "nodes_created": stats.nodes_created,
        "edges_created": stats.edges_created,
        "files_deleted": stats.files_deleted,
        "errors": stats.errors,
    }


@mcp.tool()
def annotation_status() -> dict[str, Any]:
    """Check annotation progress. Returns counts of pending/annotated/failed nodes."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    conn = store._conn  # noqa: SLF001
    cur = conn.execute(
        "SELECT annotation_status, COUNT(*) as count FROM nodes GROUP BY annotation_status"
    )
    counts: dict[str, int] = {}
    for row in cur.fetchall():
        counts[row["annotation_status"]] = row["count"]

    return {
        "pending": counts.get("pending", 0),
        "annotated": counts.get("annotated", 0),
        "failed": counts.get("failed", 0),
    }
