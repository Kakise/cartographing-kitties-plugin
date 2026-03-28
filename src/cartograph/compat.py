"""Backward-compatibility helpers for the .cartograph → .pawprints migration."""

from __future__ import annotations

import os
from pathlib import Path

# New canonical name
_DATA_DIR = ".pawprints"
# Legacy name — auto-migrated on first access
_LEGACY_DATA_DIR = ".cartograph"


def resolve_project_root() -> Path:
    """Return the resolved project root from environment variables.

    Checks ``KITTY_PROJECT_ROOT`` first, falls back to
    ``CARTOGRAPH_PROJECT_ROOT``, then ``"."``.
    """
    raw = os.environ.get("KITTY_PROJECT_ROOT") or os.environ.get("CARTOGRAPH_PROJECT_ROOT", ".")
    return Path(raw).resolve()


def resolve_db_dir(project_root: str | Path) -> Path:
    """Return the data directory, auto-migrating from legacy name if needed.

    Priority:
    1. ``.pawprints/`` already exists → use it.
    2. ``.cartograph/`` exists → rename to ``.pawprints/`` → use it.
    3. Neither exists → create ``.pawprints/``.
    """
    root = Path(project_root)
    new_dir = root / _DATA_DIR
    legacy_dir = root / _LEGACY_DATA_DIR

    if new_dir.exists():
        return new_dir

    if legacy_dir.exists():
        legacy_dir.rename(new_dir)
        return new_dir

    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir
