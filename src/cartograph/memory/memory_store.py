"""Memory store for litter-box (failures) and treat-box (successes).

Provides standalone functions for recording, querying, and exporting
memory entries from the graph store's litter_box and treat_box tables.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from cartograph.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

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


def query_entries(
    store: GraphStore,
    box: str,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    """Query memory entries from a box.

    Args:
        store: Graph store with the database connection.
        box: Which box to query (``"litter"`` or ``"treat"``).
        category: Optional category filter.
        search: Optional substring to search for in the description.
        limit: Maximum number of entries to return.

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

    return [
        MemoryEntry(
            id=row[0],
            box=box,
            category=row[1],
            description=row[2],
            context=row[3],
            created_at=row[4],
            source_agent=row[5],
        )
        for row in cur.fetchall()
    ]


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
