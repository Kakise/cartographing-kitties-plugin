"""Indexing and annotation status tools."""

from __future__ import annotations

from typing import Any

from cartograph.server.main import get_context, get_store, mcp, set_last_diff


@mcp.tool()
def index_codebase(full: bool = False) -> dict[str, Any]:
    """Trigger structural indexing of the codebase.

    Args:
        full: If True, re-index all files. If False (default), only index changed files.

    Returns stats about files parsed, nodes created, edges created.
    """
    context = get_context()
    if context is None:
        return {"error": "Server not initialised"}
    store = context.store
    root = context.root

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
    set_last_diff(diff)

    return {
        "files_parsed": stats.files_parsed,
        "nodes_created": stats.nodes_created,
        "edges_created": stats.edges_created,
        "files_deleted": stats.files_deleted,
        "errors": stats.errors,
        "diff_available": True,
        "cleanable": True,
        "diff_summary": {
            "nodes_added": diff["summary"]["nodes_added"],
            "nodes_removed": diff["summary"]["nodes_removed"],
            "nodes_modified": diff["summary"]["nodes_modified"],
        },
    }


@mcp.tool()
def annotation_status() -> dict[str, Any]:
    """Check annotation progress. Returns counts of pending/annotated/failed nodes."""
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    counts = store.annotation_status_counts()

    return {
        "pending": counts.get("pending", 0),
        "annotated": counts.get("annotated", 0),
        "failed": counts.get("failed", 0),
        "stale": counts.get("stale", 0),
        "cleanable": True,
    }
