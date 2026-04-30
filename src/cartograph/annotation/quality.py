"""Annotation quality gates and routing hints."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from cartograph.storage.graph_store import GraphStore

PLACEHOLDER_PHRASES = (
    "code node representing unknown",
    "unknown implementation",
    "source file container",
    "implementation detail",
    "function implementation",
    "class implementation",
)

GENERIC_ROLES = {"function", "file", "class", "method"}
MAX_REQUEUE_COUNT = 3


@dataclass
class RequeueStats:
    """Result from a low-quality annotation requeue pass."""

    low_quality: int = 0
    requeued: int = 0
    failed: int = 0
    dry_run: bool = True
    nodes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_low_quality(node: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return whether an annotated node looks too weak to trust."""
    reasons: list[str] = []
    summary = str(node.get("summary") or "").strip()
    summary_lower = summary.lower()

    for phrase in PLACEHOLDER_PHRASES:
        if phrase in summary_lower:
            reasons.append("placeholder_phrase")
            break

    if len(summary) < 20:
        reasons.append("summary_too_short")

    kind = str(node.get("kind") or "").lower()
    name = str(node.get("name") or "").strip()
    if kind != "file" and name and not _summary_mentions_name(summary_lower, name):
        reasons.append("missing_name_reference")

    role = _get_role(node)
    if role.strip().lower() in GENERIC_ROLES:
        reasons.append("generic_role")

    return bool(reasons), reasons


def recommended_tier(node: dict[str, Any]) -> Literal["fast", "strong"]:
    """Return the advisory model tier for a pending annotation node."""
    centrality = node.get("centrality")
    if isinstance(centrality, int | float) and centrality >= 0.5:
        return "strong"

    source = str(node.get("source") or "")
    if len(source) > 2000:
        return "strong"

    kind = str(node.get("kind") or "").lower()
    if kind in {"class", "interface"}:
        return "strong"

    return "fast"


def find_low_quality_annotations(store: GraphStore, limit: int = 100) -> list[dict[str, Any]]:
    """Return annotated nodes that fail conservative quality checks."""
    limit = max(1, min(limit, 1000))
    cur = store._conn.execute(  # noqa: SLF001
        """
        SELECT *
        FROM nodes
        WHERE annotation_status = 'annotated'
        ORDER BY id
        """
    )

    low_quality: list[dict[str, Any]] = []
    for row in cur:
        node = _row_to_node(row)
        is_low, reasons = is_low_quality(node)
        if not is_low:
            continue
        props = _properties(node)
        low_quality.append(
            {
                "id": node["id"],
                "kind": node["kind"],
                "name": node["name"],
                "qualified_name": node["qualified_name"],
                "file_path": node.get("file_path"),
                "summary": node.get("summary"),
                "reasons": reasons,
                "requeue_count": int(props.get("requeue_count", 0) or 0),
            }
        )
        if len(low_quality) >= limit:
            break
    return low_quality


def requeue_low_quality(store: GraphStore, dry_run: bool = True, limit: int = 100) -> RequeueStats:
    """Requeue low-quality annotations, or report what would change."""
    candidates = find_low_quality_annotations(store, limit=limit)
    stats = RequeueStats(low_quality=len(candidates), dry_run=dry_run, nodes=candidates)
    if dry_run or not candidates:
        return stats

    with store._conn:  # noqa: SLF001
        for candidate in candidates:
            node = store.get_node(int(candidate["id"]))
            if node is None:
                continue
            props = _properties(node)
            requeue_count = int(props.get("requeue_count", 0) or 0)
            if requeue_count >= MAX_REQUEUE_COUNT:
                props["requeue_reason"] = candidate["reasons"]
                props["requeue_count"] = requeue_count
                store._conn.execute(  # noqa: SLF001
                    """
                    UPDATE nodes
                    SET annotation_status = 'failed',
                        properties = ?,
                        updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (json.dumps(props), candidate["id"]),
                )
                stats.failed += 1
                continue

            props["requeue_reason"] = candidate["reasons"]
            props["requeue_count"] = requeue_count + 1
            store._conn.execute(  # noqa: SLF001
                """
                UPDATE nodes
                SET annotation_status = 'pending',
                    properties = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (json.dumps(props), candidate["id"]),
            )
            stats.requeued += 1

    return stats


def _summary_mentions_name(summary_lower: str, name: str) -> bool:
    for variant in _name_variants(name):
        if variant and variant in summary_lower:
            return True
    return False


def _name_variants(name: str) -> set[str]:
    variants = {name.lower()}
    separated = re.sub(r"[_\-]+", " ", name).strip().lower()
    if separated:
        variants.add(separated)
    camel_spaced = re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip().lower()
    if camel_spaced:
        variants.add(camel_spaced)
    return variants


def _get_role(node: dict[str, Any]) -> str:
    role = node.get("role")
    if isinstance(role, str):
        return role
    props = _properties(node)
    role = props.get("role")
    return role if isinstance(role, str) else ""


def _properties(node: dict[str, Any]) -> dict[str, Any]:
    props = node.get("properties")
    if isinstance(props, str):
        try:
            parsed = json.loads(props)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return props if isinstance(props, dict) else {}


def _row_to_node(row: Any) -> dict[str, Any]:
    node = dict(row)
    if "properties" in node:
        node["properties"] = _properties(node)
    return node
