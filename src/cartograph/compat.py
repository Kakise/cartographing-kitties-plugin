"""Storage path helpers and .cartograph → .pawprints compatibility."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

# New canonical name
_DATA_DIR = ".pawprints"
# Legacy name — auto-migrated on first access
_LEGACY_DATA_DIR = ".cartograph"
_DB_NAME = "graph.db"
_TREAT_BOX_NAME = "treat-box.md"
_LITTER_BOX_NAME = "litter-box.md"


@dataclass(frozen=True)
class StoragePaths:
    """Resolved storage locations for one project."""

    project_root: Path
    storage_root: Path
    data_dir: Path
    db_path: Path
    treat_box_path: Path
    litter_box_path: Path


def resolve_project_root(project_root: str | Path | None = None) -> Path:
    """Return the resolved project root from argument or environment.

    Priority:
    1. Explicit *project_root* argument
    2. ``KITTY_PROJECT_ROOT``
    3. ``CARTOGRAPH_PROJECT_ROOT``
    4. ``"."``
    """
    if project_root is not None:
        return Path(project_root).resolve()

    raw = os.environ.get("KITTY_PROJECT_ROOT") or os.environ.get("CARTOGRAPH_PROJECT_ROOT", ".")
    return Path(raw).resolve()


def resolve_storage_root(storage_root: str | Path | None = None) -> Path | None:
    """Return an explicit centralized storage root, if configured."""
    if storage_root is not None:
        return Path(storage_root).resolve()

    raw = os.environ.get("KITTY_STORAGE_ROOT") or os.environ.get("CARTOGRAPH_STORAGE_ROOT")
    if raw is None:
        return None
    return Path(raw).resolve()


def _resolve_local_data_dir(project_root: Path) -> Path:
    """Return the local project data directory, migrating from legacy name if needed.

    Priority:
    1. ``.pawprints/`` already exists → use it.
    2. ``.cartograph/`` exists → rename to ``.pawprints/`` → use it.
    3. Neither exists → create ``.pawprints/``.
    """
    new_dir = project_root / _DATA_DIR
    legacy_dir = project_root / _LEGACY_DATA_DIR

    if new_dir.exists():
        return new_dir

    if legacy_dir.exists():
        legacy_dir.rename(new_dir)
        return new_dir

    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir


def _slugify_project_name(project_root: Path) -> str:
    """Return a stable, human-readable slug for the project directory name."""
    slug = re.sub(r"[^a-z0-9]+", "-", project_root.name.lower()).strip("-")
    return slug or "project"


def derive_project_storage_dir(project_root: str | Path, storage_root: str | Path) -> Path:
    """Return the per-project data directory under a centralized storage root."""
    resolved_project_root = Path(project_root).resolve()
    resolved_storage_root = Path(storage_root).resolve()
    slug = _slugify_project_name(resolved_project_root)
    digest = hashlib.sha256(str(resolved_project_root).encode("utf-8")).hexdigest()[:10]
    return resolved_storage_root / f"{slug}-{digest}"


def resolve_storage_paths(
    project_root: str | Path | None = None,
    *,
    storage_root: str | Path | None = None,
) -> StoragePaths:
    """Resolve all storage paths for the requested project."""
    resolved_project_root = resolve_project_root(project_root)
    resolved_storage_root = resolve_storage_root(storage_root)

    if resolved_storage_root is None:
        data_dir = _resolve_local_data_dir(resolved_project_root)
        storage_root_path = resolved_project_root
    else:
        storage_root_path = resolved_storage_root
        storage_root_path.mkdir(parents=True, exist_ok=True)
        data_dir = derive_project_storage_dir(resolved_project_root, storage_root_path)
        data_dir.mkdir(parents=True, exist_ok=True)

    return StoragePaths(
        project_root=resolved_project_root,
        storage_root=storage_root_path,
        data_dir=data_dir,
        db_path=data_dir / _DB_NAME,
        treat_box_path=data_dir / _TREAT_BOX_NAME,
        litter_box_path=data_dir / _LITTER_BOX_NAME,
    )


def resolve_db_dir(
    project_root: str | Path,
    *,
    storage_root: str | Path | None = None,
) -> Path:
    """Return the resolved data directory for backwards compatibility."""
    return resolve_storage_paths(project_root, storage_root=storage_root).data_dir
