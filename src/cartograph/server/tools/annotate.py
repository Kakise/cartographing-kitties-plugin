"""Annotation tools for agent-delegated annotation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from cartograph.server.main import get_context, get_store, mcp
from cartograph.server.tools.query import summarise_node


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
    context = get_context()
    if context is None:
        return {"error": "Server not initialised"}
    store = context.store
    root = context.root

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
def submit_annotations(annotations: list[Any]) -> dict[str, Any]:
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
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.annotation import AnnotationResult, write_annotations

    results: list[AnnotationResult] = []
    skipped_input = 0
    for item in annotations:
        if not isinstance(item, dict):
            skipped_input += 1
            continue
        annotation = cast(dict[str, Any], item)
        raw_tags = annotation.get("tags", [])
        tag_values = cast(list[Any], raw_tags) if isinstance(raw_tags, list) else []
        tags = [tag for tag in tag_values if isinstance(tag, str)]
        results.append(
            AnnotationResult(
                qualified_name=str(annotation.get("qualified_name", "")),
                summary=str(annotation.get("summary", "")),
                tags=tags,
                role=str(annotation.get("role", "")),
                failed=bool(annotation.get("failed", False)),
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


@mcp.tool()
def find_stale_annotations(file_paths: list[str] | None = None, limit: int = 50) -> dict[str, Any]:
    """Find nodes whose code changed since they were annotated.

    A node is stale when its content_hash (set by the indexer) differs from
    its annotated_content_hash (set when annotations were written). Pre-migration
    annotated nodes with no annotated_content_hash are also considered stale.

    Args:
        file_paths: Optional list of file paths to restrict the search to.
        limit: Maximum number of stale nodes to return (default 50).

    Returns:
        Dict with count and list of stale node summaries.
    """
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    stale = store.find_stale_nodes(file_paths=file_paths, limit=limit)
    return {
        "count": len(stale),
        "stale_nodes": [{**summarise_node(n), "reason": "content_hash_changed"} for n in stale],
    }


@mcp.tool()
def find_low_quality_annotations(limit: int = 100) -> dict[str, Any]:
    """Find annotated nodes with placeholder or generic annotation quality.

    Args:
        limit: Maximum number of annotated nodes to inspect (default 100).

    Returns:
        Dict with count and low-quality node summaries including reasons.
    """
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.annotation.quality import find_low_quality_annotations as find_low_quality

    nodes = find_low_quality(store, limit=limit)
    return {"count": len(nodes), "low_quality_nodes": nodes}


@mcp.tool()
def requeue_low_quality_annotations(dry_run: bool = True, limit: int = 100) -> dict[str, Any]:
    """Requeue low-quality annotations so the next annotation pass rewrites them.

    Args:
        dry_run: If True, report what would be requeued without mutating the DB.
        limit: Maximum number of annotated nodes to inspect (default 100).

    Returns:
        Dict with low-quality, requeued, failed, and dry-run counts.
    """
    store = get_store()
    if store is None:
        return {"error": "Server not initialised"}

    from cartograph.annotation.quality import requeue_low_quality

    return requeue_low_quality(store, dry_run=dry_run, limit=limit).to_dict()
