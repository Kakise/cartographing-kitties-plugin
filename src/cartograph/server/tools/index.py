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

    # Snapshot nodes and edges BEFORE indexing for diff computation.
    # For full re-index, snapshot everything; for incremental, also snapshot
    # everything (since we don't know which files will change until after).
    before_nodes = store.snapshot_nodes()
    before_edges = store.snapshot_edges()

    indexer = Indexer(root, store)
    stats = indexer.index_all() if full else indexer.index_changed()

    # Snapshot AFTER indexing and compute diff.
    after_nodes = store.snapshot_nodes()
    after_edges = store.snapshot_edges()
    diff = store.compute_diff(before_nodes, after_nodes, before_edges, after_edges)

    # Store diff for graph_diff tool to retrieve.
    _main._last_diff = diff

    return {
        "files_parsed": stats.files_parsed,
        "nodes_created": stats.nodes_created,
        "edges_created": stats.edges_created,
        "files_deleted": stats.files_deleted,
        "errors": stats.errors,
        "diff_available": True,
        "diff_summary": {
            "nodes_added": diff["summary"]["nodes_added"],
            "nodes_removed": diff["summary"]["nodes_removed"],
            "nodes_modified": diff["summary"]["nodes_modified"],
        },
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

    stale_cur = conn.execute(
        """
        SELECT COUNT(*) FROM nodes
        WHERE annotation_status = 'annotated'
        AND content_hash IS NOT NULL
        AND (annotated_content_hash IS NULL OR content_hash != annotated_content_hash)
        """
    )
    stale_count = stale_cur.fetchone()[0]

    return {
        "pending": counts.get("pending", 0),
        "annotated": counts.get("annotated", 0),
        "failed": counts.get("failed", 0),
        "stale": stale_count,
    }
