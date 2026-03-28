"""Annotation tools for agent-delegated annotation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import cartograph.server.main as _main
from cartograph.server.main import mcp


@mcp.tool()
def get_pending_annotations(batch_size: int = 10, retry_failed: bool = False) -> dict[str, Any]:
    """Get pending nodes with full context for annotation.

    Returns a batch of nodes with their source code, metadata, and neighbor
    context so the host agent can generate summaries and tags.

    Args:
        batch_size: Maximum number of nodes to return (default 10, max 100).
        retry_failed: If True, also include nodes with annotation_status='failed'.

    Returns:
        Dict with batch of node contexts, the seed taxonomy, and count.
    """
    store = _main._store
    root = _main._root
    if store is None:
        return {"error": "Server not initialised"}

    batch_size = max(1, min(batch_size, 100))

    from cartograph.annotation import SEED_TAXONOMY, get_pending_nodes

    nodes = get_pending_nodes(
        store, batch_size=batch_size, source_root=root, retry_failed=retry_failed
    )

    return {
        "batch": [asdict(n) for n in nodes],
        "taxonomy": SEED_TAXONOMY,
        "count": len(nodes),
    }


@mcp.tool()
def submit_annotations(annotations: list[dict]) -> dict[str, Any]:
    """Submit annotation results for pending nodes.

    Each annotation dict should have:
        - qualified_name (str): identifies the node
        - summary (str): one-sentence summary
        - tags (list[str]): suggested tags
        - role (str): short role description
        - failed (bool, optional): set True to mark as failed

    Args:
        annotations: List of annotation result dicts.

    Returns:
        Dict with written, failed, and skipped counts.
    """
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.annotation import AnnotationResult, write_annotations

    results: list[AnnotationResult] = []
    skipped_input = 0
    for a in annotations:
        if not isinstance(a, dict):
            skipped_input += 1
            continue
        results.append(
            AnnotationResult(
                qualified_name=a.get("qualified_name", ""),
                summary=a.get("summary", ""),
                tags=a.get("tags", []) if isinstance(a.get("tags"), list) else [],
                role=a.get("role", ""),
                failed=a.get("failed", False),
            )
        )

    try:
        stats = write_annotations(store, results)
    except Exception as exc:
        return {
            "error": f"Write failed: {exc}",
            "written": 0,
            "failed": 0,
            "skipped": skipped_input,
        }

    return {
        "written": stats.written,
        "failed": stats.failed,
        "skipped": stats.skipped + skipped_input,
    }
