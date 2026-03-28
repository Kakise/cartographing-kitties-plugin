"""File discovery and change detection for Cartograph indexing."""

from __future__ import annotations

import fnmatch
import hashlib
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cartograph.storage.graph_store import GraphStore

DEFAULT_EXTENSIONS: set[str] = {".py", ".ts", ".tsx", ".js", ".jsx"}

EXCLUDED_DIRS: set[str] = {
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".git",
    ".cartograph",
    ".pawprints",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "env",
    ".eggs",
    "egg-info",
}


@dataclass
class ChangedFiles:
    new: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    deleted: list[Path] = field(default_factory=list)


def _parse_gitignore(root_path: Path) -> list[str]:
    """Read .gitignore and return a list of patterns."""
    gitignore = root_path / ".gitignore"
    if not gitignore.is_file():
        return []
    patterns: list[str] = []
    for line in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_gitignored(rel_path: Path, patterns: list[str]) -> bool:
    """Check whether a relative path matches any gitignore pattern."""
    rel_str = str(rel_path)
    for pattern in patterns:
        # Directory pattern (e.g. "dist/")
        if pattern.endswith("/"):
            dir_pat = pattern.rstrip("/")
            for part in rel_path.parts:
                if fnmatch.fnmatch(part, dir_pat):
                    return True
        else:
            # Match against the filename
            if fnmatch.fnmatch(rel_path.name, pattern):
                return True
            # Also try matching the full relative path
            if fnmatch.fnmatch(rel_str, pattern):
                return True
    return False


def discover_files(
    root_path: Path,
    extensions: set[str] | None = None,
) -> list[Path]:
    """Walk directory tree and return sorted list of matching files (relative to root)."""
    if extensions is None:
        extensions = DEFAULT_EXTENSIONS

    gitignore_patterns = _parse_gitignore(root_path)
    results: list[Path] = []

    def _walk(directory: Path) -> None:
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            return

        for entry in entries:
            # Don't follow symlinks
            if entry.is_symlink():
                continue

            rel = entry.relative_to(root_path)

            if entry.is_dir():
                # Skip excluded and hidden directories
                if entry.name in EXCLUDED_DIRS:
                    continue
                if entry.name.startswith("."):
                    continue
                if gitignore_patterns and _is_gitignored(rel, gitignore_patterns):
                    continue
                _walk(entry)
            elif entry.is_file():
                if entry.suffix not in extensions:
                    continue
                if gitignore_patterns and _is_gitignored(rel, gitignore_patterns):
                    continue
                results.append(rel)

    _walk(root_path)
    return sorted(results)


def compute_file_hash(file_path: Path) -> str:
    """Return SHA256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_changes(root_path: Path, graph_store: object) -> ChangedFiles:
    """Detect new, modified, and deleted files compared to the graph store.

    Tries git diff first; falls back to content hash comparison.
    """
    from cartograph.storage.graph_store import GraphStore

    assert isinstance(graph_store, GraphStore)

    # Discover files currently on disk
    disk_files = discover_files(root_path)

    # Try git-based detection first
    git_changed = _try_git_diff(root_path)
    if git_changed is not None:
        return _categorize_git_changes(root_path, disk_files, git_changed, graph_store)

    # Fallback: content hash comparison
    return _hash_based_changes(root_path, disk_files, graph_store)


def _try_git_diff(root_path: Path) -> set[str] | None:
    """Run git diff --name-only HEAD; return set of changed file paths or None on failure."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(root_path),
            timeout=10,
        )
        if result.returncode != 0:
            return None
        names = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return names
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return None


def _categorize_git_changes(
    root_path: Path,
    disk_files: list[Path],
    git_changed: set[str],
    graph_store: GraphStore,
) -> ChangedFiles:
    """Use git diff output + stored hashes to categorize changes."""

    stored_hashes = graph_store.get_content_hashes()
    disk_set = {str(p) for p in disk_files}
    changed = ChangedFiles()

    for f in disk_files:
        f_str = str(f)
        if f_str not in stored_hashes:
            changed.new.append(f)
        elif f_str in git_changed:
            changed.modified.append(f)

    for f_str in stored_hashes:
        if f_str not in disk_set:
            changed.deleted.append(Path(f_str))

    changed.new.sort()
    changed.modified.sort()
    changed.deleted.sort()
    return changed


def _hash_based_changes(
    root_path: Path,
    disk_files: list[Path],
    graph_store: GraphStore,
) -> ChangedFiles:
    """Compare file hashes against stored hashes."""

    stored_hashes = graph_store.get_content_hashes()
    disk_set = {str(p) for p in disk_files}
    changed = ChangedFiles()

    for f in disk_files:
        f_str = str(f)
        current_hash = compute_file_hash(root_path / f)
        if f_str not in stored_hashes:
            changed.new.append(f)
        elif stored_hashes[f_str] != current_hash:
            changed.modified.append(f)

    for f_str in stored_hashes:
        if f_str not in disk_set:
            changed.deleted.append(Path(f_str))

    changed.new.sort()
    changed.modified.sort()
    changed.deleted.sort()
    return changed
