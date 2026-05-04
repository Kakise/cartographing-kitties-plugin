"""Memory store for litter-box (failures) and treat-box (successes).

Provides standalone functions for recording, querying, and exporting
memory entries from the graph store's litter_box and treat_box tables.
Also covers the agent-handoff store used by the orchestrator to pass
sub-agent run results across compaction boundaries.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cartograph.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

DEFAULT_HANDOFF_TTL_SECONDS = 86_400  # 24 hours
LONG_RUNNING_HANDOFF_TTL_SECONDS = 604_800  # 7 days
_VALID_HANDOFF_ROLES = {"annotation", "research", "review"}

_VALID_BOXES = {"litter", "treat"}

_TABLE_MAP = {
    "litter": "litter_box",
    "treat": "treat_box",
}

_VALID_CATEGORIES = {
    "litter": {"failure", "anti-pattern", "unsupported", "regression", "never-do"},
    "treat": {"best-practice", "validated-pattern", "always-do", "convention", "optimization"},
}


@dataclass
class MemoryEntry:
    """A single memory entry from the litter or treat box."""

    id: int
    box: str
    category: str
    description: str
    context: str
    created_at: str
    source_agent: str
    relevance_score: float = 0.0


@dataclass
class HandoffRecord:
    """A persisted unified-output payload from a framework subagent."""

    run_id: str
    session_id: str
    agent_name: str
    role: str
    payload: dict[str, Any]
    created_at: int
    expires_at: int


def _validate_box(box: str) -> str:
    """Validate and return the table name for the given box."""
    if box not in _VALID_BOXES:
        msg = f"Invalid box {box!r}; must be one of {sorted(_VALID_BOXES)}"
        raise ValueError(msg)
    return _TABLE_MAP[box]


def add_entry(
    store: GraphStore,
    box: str,
    category: str,
    description: str,
    context: str = "",
    source_agent: str = "",
) -> int:
    """Insert a memory entry into the appropriate table.

    Args:
        store: Graph store with the database connection.
        box: Which box to insert into (``"litter"`` or ``"treat"``).
        category: Entry category (must match the table's CHECK constraint).
        description: Description of the memory.
        context: Optional additional context.
        source_agent: Optional identifier of the agent that created the entry.

    Returns:
        The row ID of the newly inserted entry.
    """
    table = _validate_box(box)
    valid_cats = _VALID_CATEGORIES[box]
    if category not in valid_cats:
        msg = f"Invalid category {category!r} for {box} box; must be one of {sorted(valid_cats)}"
        raise ValueError(msg)

    conn = store._conn  # noqa: SLF001
    cur = conn.execute(
        f"INSERT INTO {table} (category, description, context, source_agent) VALUES (?, ?, ?, ?)",  # noqa: S608
        (category, description, context, source_agent),
    )
    conn.commit()
    return cur.lastrowid  # type: ignore[return-value]


def _approximate_token_count(value: str) -> int:
    """Cheap token estimate (len/4). Matches the U2 fallback approximation."""

    return max(1, len(value) // 4)


def _score_relevance(description: str, search: str | None) -> float:
    """Lightweight LIKE-based relevance scorer (substring count + length penalty)."""

    if not search:
        return 0.0
    needle = search.lower()
    haystack = description.lower()
    if not needle:
        return 0.0
    occurrences = haystack.count(needle)
    if occurrences == 0:
        return 0.0
    # Normalise by description length so short, on-topic entries beat long ones.
    base = occurrences / max(1, len(haystack) // 80 + 1)
    return round(min(1.0, base), 3)


def query_entries(
    store: GraphStore,
    box: str,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    token_budget: int | None = None,
) -> list[MemoryEntry]:
    """Query memory entries from a box.

    Args:
        store: Graph store with the database connection.
        box: Which box to query (``"litter"`` or ``"treat"``).
        category: Optional category filter.
        search: Optional substring to search for in the description.
        limit: Maximum number of entries to return.
        token_budget: Optional token budget (approximate). When set, entries are
            ranked by relevance and accumulated only while the running total
            stays within budget.

    Returns:
        List of matching :class:`MemoryEntry` objects.
    """
    table = _validate_box(box)
    conn = store._conn  # noqa: SLF001

    clauses: list[str] = []
    params: list[str | int] = []

    if category is not None:
        clauses.append("category = ?")
        params.append(category)
    if search is not None:
        clauses.append("description LIKE ?")
        params.append(f"%{search}%")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    cur = conn.execute(
        f"SELECT id, category, description, context, created_at, source_agent FROM {table}{where} ORDER BY created_at DESC LIMIT ?",  # noqa: S608
        params,
    )

    entries = [
        MemoryEntry(
            id=row[0],
            box=box,
            category=row[1],
            description=row[2],
            context=row[3],
            created_at=row[4],
            source_agent=row[5],
            relevance_score=_score_relevance(row[2], search),
        )
        for row in cur.fetchall()
    ]

    if token_budget is None:
        return entries

    # Re-rank by relevance (descending), preserving recency as the tiebreaker.
    ranked = sorted(entries, key=lambda e: (-e.relevance_score, -entries.index(e)))
    accumulated: list[MemoryEntry] = []
    used_tokens = 0
    for entry in ranked:
        cost = _approximate_token_count(entry.description) + _approximate_token_count(entry.context)
        if used_tokens + cost > token_budget:
            break
        accumulated.append(entry)
        used_tokens += cost
    return accumulated


def export_markdown(store: GraphStore, box: str, output_path: Path | str) -> int:
    """Export all entries from a box to a markdown file, grouped by category.

    Args:
        store: Graph store with the database connection.
        box: Which box to export (``"litter"`` or ``"treat"``).
        output_path: Path to write the markdown file.

    Returns:
        Total number of entries exported.
    """
    table = _validate_box(box)
    conn = store._conn  # noqa: SLF001

    cur = conn.execute(
        f"SELECT id, category, description, context, created_at, source_agent FROM {table} ORDER BY category, created_at",  # noqa: S608
    )
    rows = cur.fetchall()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = "Litter Box" if box == "litter" else "Treat Box"
    lines: list[str] = [f"# {title}\n"]

    current_category: str | None = None
    for row in rows:
        _id, category, description, context, created_at, source_agent = row
        if category != current_category:
            current_category = category
            lines.append(f"\n## {category}\n")
        entry_line = f"- **{description}**"
        if context:
            entry_line += f" -- {context}"
        if source_agent:
            entry_line += f" _(agent: {source_agent})_"
        lines.append(entry_line)

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


# ---------------------------------------------------------------------------
# Agent handoff store
# ---------------------------------------------------------------------------


def stage_handoff(
    store: GraphStore,
    session_id: str,
    agent_name: str,
    role: str,
    payload: dict[str, Any],
    ttl_seconds: int = DEFAULT_HANDOFF_TTL_SECONDS,
    *,
    now: int | None = None,
) -> str:
    """Persist a unified-output payload and return its ``run_id``.

    The orchestrator passes the returned ``run_id`` through the conversation;
    callers reload the payload via :func:`get_handoff` only when synthesizing.
    """

    if role not in _VALID_HANDOFF_ROLES:
        msg = f"Invalid handoff role {role!r}; must be one of {sorted(_VALID_HANDOFF_ROLES)}"
        raise ValueError(msg)
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    run_id = uuid.uuid4().hex
    created_at = now if now is not None else int(time.time())
    expires_at = created_at + ttl_seconds
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    conn = store._conn  # noqa: SLF001
    conn.execute(
        "INSERT INTO agent_handoffs (run_id, session_id, agent_name, role, payload, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (run_id, session_id, agent_name, role, serialized, created_at, expires_at),
    )
    conn.commit()
    return run_id


def get_handoff(
    store: GraphStore,
    run_id: str,
    *,
    now: int | None = None,
) -> HandoffRecord | None:
    """Fetch a staged payload by ``run_id``. Expired records return ``None``."""

    current = now if now is not None else int(time.time())
    conn = store._conn  # noqa: SLF001
    row = conn.execute(
        "SELECT run_id, session_id, agent_name, role, payload, created_at, expires_at "
        "FROM agent_handoffs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    if int(row[6]) <= current:
        return None
    return HandoffRecord(
        run_id=row[0],
        session_id=row[1],
        agent_name=row[2],
        role=row[3],
        payload=json.loads(row[4]),
        created_at=int(row[5]),
        expires_at=int(row[6]),
    )


def expire_handoffs(store: GraphStore, *, now: int | None = None) -> int:
    """Delete handoff records whose ``expires_at`` is in the past.

    Returns the number of rows deleted. Cheap to run on every ``stage_handoff``
    call when storage cleanliness matters; otherwise can be invoked on demand.
    """

    current = now if now is not None else int(time.time())
    conn = store._conn  # noqa: SLF001
    cur = conn.execute(
        "DELETE FROM agent_handoffs WHERE expires_at <= ?",
        (current,),
    )
    conn.commit()
    return cur.rowcount or 0
