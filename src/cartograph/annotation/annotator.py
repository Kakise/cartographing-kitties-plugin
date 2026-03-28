"""Annotation data-gathering and submission helpers.

Provides standalone functions for the host agent to read pending nodes with
full context and write annotation results back to the graph store.  The LLM
calling parts have been removed -- the host agent itself generates summaries
and tags using its own model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cartograph.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

SEED_TAXONOMY = [
    "auth",
    "database",
    "api",
    "config",
    "testing",
    "logging",
    "validation",
    "serialization",
    "middleware",
    "routing",
    "models",
    "services",
    "utilities",
    "error-handling",
    "caching",
]

# Map common synonyms / variations to canonical seed taxonomy terms.
_TAG_SYNONYMS: dict[str, str] = {
    "authentication": "auth",
    "authorization": "auth",
    "db": "database",
    "sql": "database",
    "orm": "database",
    "rest": "api",
    "http": "api",
    "endpoint": "api",
    "endpoints": "api",
    "configuration": "config",
    "settings": "config",
    "test": "testing",
    "tests": "testing",
    "log": "logging",
    "validate": "validation",
    "validator": "validation",
    "serialize": "serialization",
    "deserialize": "serialization",
    "json": "serialization",
    "route": "routing",
    "routes": "routing",
    "router": "routing",
    "model": "models",
    "schema": "models",
    "service": "services",
    "util": "utilities",
    "utils": "utilities",
    "helper": "utilities",
    "helpers": "utilities",
    "error": "error-handling",
    "errors": "error-handling",
    "exception": "error-handling",
    "exceptions": "error-handling",
    "cache": "caching",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class NodeContext:
    """Full context for a pending node ready for annotation."""

    id: int
    kind: str
    name: str
    qualified_name: str
    file_path: str | None
    start_line: int | None
    end_line: int | None
    language: str | None
    source: str
    neighbors: list[dict[str, Any]]


@dataclass
class AnnotationResult:
    """A single annotation result to write back to the graph store."""

    qualified_name: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    role: str = ""
    failed: bool = False


@dataclass
class WriteStats:
    """Statistics from a write_annotations call."""

    written: int = 0
    failed: int = 0
    skipped: int = 0


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def get_pending_nodes(
    store: GraphStore,
    batch_size: int = 10,
    retry_failed: bool = False,
    source_root: Path | None = None,
) -> list[NodeContext]:
    """Query pending nodes with full context for annotation.

    Args:
        store: Graph store to query.
        batch_size: Maximum number of nodes to return.
        retry_failed: If True, include nodes with annotation_status='failed'.
        source_root: Root directory for resolving relative file paths.

    Returns:
        List of NodeContext objects with source code and neighbor info.
    """
    conn = store._conn  # noqa: SLF001
    statuses = ["pending"]
    if retry_failed:
        statuses.append("failed")
    placeholders = ", ".join("?" for _ in statuses)
    cur = conn.execute(
        f"SELECT * FROM nodes WHERE annotation_status IN ({placeholders}) LIMIT ?",
        statuses + [batch_size],
    )
    rows = cur.fetchall()

    result: list[NodeContext] = []
    for row in rows:
        node = dict(row)
        if "properties" in node and node["properties"] is not None:
            try:
                node["properties"] = json.loads(node["properties"])
            except (json.JSONDecodeError, TypeError):
                pass

        source = extract_source(
            file_path=node.get("file_path", ""),
            start_line=node.get("start_line"),
            end_line=node.get("end_line"),
            source_root=source_root,
        )

        # Gather immediate neighbors (outgoing and incoming edges).
        neighbors: list[dict[str, Any]] = []
        node_id = node.get("id")
        if node_id is not None:
            for edge in store.get_edges(source_id=node_id):
                target = store.get_node(edge["target_id"])
                if target:
                    neighbors.append(
                        {
                            "direction": "outgoing",
                            "edge_kind": edge["kind"],
                            "kind": target["kind"],
                            "qualified_name": target["qualified_name"],
                        }
                    )
            for edge in store.get_edges(target_id=node_id):
                src = store.get_node(edge["source_id"])
                if src:
                    neighbors.append(
                        {
                            "direction": "incoming",
                            "edge_kind": edge["kind"],
                            "kind": src["kind"],
                            "qualified_name": src["qualified_name"],
                        }
                    )

        result.append(
            NodeContext(
                id=node["id"],
                kind=node["kind"],
                name=node["name"],
                qualified_name=node["qualified_name"],
                file_path=node.get("file_path"),
                start_line=node.get("start_line"),
                end_line=node.get("end_line"),
                language=node.get("language"),
                source=source,
                neighbors=neighbors,
            )
        )

    return result


def write_annotations(
    store: GraphStore,
    results: list[AnnotationResult],
) -> WriteStats:
    """Write annotation results back to the graph store.

    Args:
        store: Graph store to update.
        results: List of AnnotationResult objects.

    Returns:
        WriteStats with counts of written, failed, and skipped nodes.
    """
    stats = WriteStats()

    if not results:
        return stats

    upsert_batch: list[dict] = []

    for result in results:
        try:
            node = store.get_node_by_name(result.qualified_name)
        except Exception:
            stats.skipped += 1
            continue

        if node is None:
            stats.skipped += 1
            continue

        if result.failed:
            upsert_batch.append(
                {
                    "kind": node["kind"],
                    "name": node["name"],
                    "qualified_name": node["qualified_name"],
                    "file_path": node.get("file_path"),
                    "start_line": node.get("start_line"),
                    "end_line": node.get("end_line"),
                    "language": node.get("language"),
                    "summary": node.get("summary"),
                    "annotation_status": "failed",
                    "content_hash": node.get("content_hash"),
                    "properties": node.get("properties"),
                }
            )
            stats.failed += 1
        else:
            tags = normalize_tags(result.tags)
            existing_props = node.get("properties")
            if isinstance(existing_props, str):
                try:
                    existing_props = json.loads(existing_props)
                except (json.JSONDecodeError, TypeError):
                    existing_props = {}
            if not isinstance(existing_props, dict):
                existing_props = {}

            upsert_batch.append(
                {
                    "kind": node["kind"],
                    "name": node["name"],
                    "qualified_name": node["qualified_name"],
                    "file_path": node.get("file_path"),
                    "start_line": node.get("start_line"),
                    "end_line": node.get("end_line"),
                    "language": node.get("language"),
                    "summary": result.summary,
                    "annotation_status": "annotated",
                    "content_hash": node.get("content_hash"),
                    "properties": {
                        **existing_props,
                        "tags": tags,
                        "role": result.role,
                    },
                }
            )
            stats.written += 1

    if upsert_batch:
        try:
            store.upsert_nodes(upsert_batch)
        except Exception:
            logger.exception("Failed to write annotation batch")
            # Re-throw so the caller knows the write failed.
            raise

    return stats


def normalize_tags(tags: list[str]) -> list[str]:
    """Normalise tags: lowercase, prefer seed taxonomy terms."""
    normalised: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        t = tag.lower().strip()
        # Map synonyms to canonical terms.
        t = _TAG_SYNONYMS.get(t, t)
        if t and t not in seen:
            normalised.append(t)
            seen.add(t)
    return normalised


def extract_source(
    file_path: str,
    start_line: int | None,
    end_line: int | None,
    source_root: Path | None = None,
) -> str:
    """Extract source code for a node from its file.

    Args:
        file_path: Path to the source file (may be relative).
        start_line: Start line (1-indexed), or None for whole file.
        end_line: End line (1-indexed), or None for whole file.
        source_root: Root directory for resolving relative paths.

    Returns:
        Source code text, or "(source unavailable)" if the file cannot be read.
    """
    if not file_path:
        return "(source unavailable)"

    path = Path(file_path)
    if source_root and not path.is_absolute():
        path = source_root / path

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "(source unavailable)"

    if start_line is not None and end_line is not None:
        # Lines are 1-indexed in the DB.
        return "\n".join(lines[max(0, start_line - 1) : end_line])
    return "\n".join(lines)
