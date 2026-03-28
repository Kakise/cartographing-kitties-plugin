"""Tests for cartograph.indexing.discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from cartograph.indexing.discovery import (
    compute_file_hash,
    detect_changes,
    discover_files,
)
from cartograph.storage import GraphStore, create_connection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(base: Path, rel: str, content: str = "# placeholder\n") -> Path:
    """Create a file inside base at relative path rel."""
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _make_graph_store(tmp_path: Path) -> GraphStore:
    """Create an in-memory GraphStore backed by a temp SQLite DB."""
    db_path = tmp_path / "test.db"
    conn = create_connection(db_path)
    return GraphStore(conn)


# ---------------------------------------------------------------------------
# 1. Discover Python and TypeScript files; node_modules/__pycache__ excluded
# ---------------------------------------------------------------------------


def test_discover_excludes_node_modules_and_pycache(tmp_path: Path) -> None:
    _make_file(tmp_path, "app.py")
    _make_file(tmp_path, "component.tsx")
    _make_file(tmp_path, "node_modules/pkg/index.js")
    _make_file(tmp_path, "__pycache__/mod.cpython-311.pyc")
    _make_file(tmp_path, "src/lib.py")

    found = discover_files(tmp_path)
    names = [str(p) for p in found]

    assert "app.py" in names
    assert "component.tsx" in names
    assert "src/lib.py" in names
    # excluded dirs
    assert not any("node_modules" in n for n in names)
    assert not any("__pycache__" in n for n in names)


# ---------------------------------------------------------------------------
# 2. Only files with specified extensions are returned
# ---------------------------------------------------------------------------


def test_discover_custom_extensions(tmp_path: Path) -> None:
    _make_file(tmp_path, "main.py")
    _make_file(tmp_path, "data.csv")
    _make_file(tmp_path, "readme.md")
    _make_file(tmp_path, "style.css")

    found = discover_files(tmp_path, extensions={".csv", ".md"})
    names = {str(p) for p in found}

    assert names == {"data.csv", "readme.md"}


# ---------------------------------------------------------------------------
# 3. Hidden directories are excluded
# ---------------------------------------------------------------------------


def test_discover_skips_hidden_dirs(tmp_path: Path) -> None:
    _make_file(tmp_path, "visible/mod.py")
    _make_file(tmp_path, ".hidden/secret.py")

    found = discover_files(tmp_path)
    names = [str(p) for p in found]

    assert "visible/mod.py" in names
    assert not any(".hidden" in n for n in names)


# ---------------------------------------------------------------------------
# 4. detect_changes with no prior hashes: all files are "new"
# ---------------------------------------------------------------------------


def test_detect_changes_all_new(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _make_file(root, "a.py", "print('a')\n")
    _make_file(root, "b.py", "print('b')\n")

    store = _make_graph_store(tmp_path)

    changes = detect_changes(root, store)

    assert len(changes.new) == 2
    assert len(changes.modified) == 0
    assert len(changes.deleted) == 0
    store.close()


# ---------------------------------------------------------------------------
# 5. detect_changes with matching hashes: no changes
# ---------------------------------------------------------------------------


def test_detect_changes_no_changes(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _make_file(root, "a.py", "print('a')\n")

    store = _make_graph_store(tmp_path)

    # Simulate prior indexing by inserting a file node with the correct hash
    file_hash = compute_file_hash(root / "a.py")
    store.upsert_nodes(
        [
            {
                "kind": "file",
                "name": "a.py",
                "qualified_name": "file::a.py",
                "file_path": "a.py",
                "content_hash": file_hash,
            }
        ]
    )

    changes = detect_changes(root, store)

    assert len(changes.new) == 0
    assert len(changes.modified) == 0
    assert len(changes.deleted) == 0
    store.close()


# ---------------------------------------------------------------------------
# 6. detect_changes with modified file
# ---------------------------------------------------------------------------


def test_detect_changes_modified(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _make_file(root, "a.py", "print('a')\n")

    store = _make_graph_store(tmp_path)

    # Insert node with an OLD hash (different from current)
    store.upsert_nodes(
        [
            {
                "kind": "file",
                "name": "a.py",
                "qualified_name": "file::a.py",
                "file_path": "a.py",
                "content_hash": "oldhash000",
            }
        ]
    )

    changes = detect_changes(root, store)

    assert len(changes.modified) == 1
    assert Path("a.py") in changes.modified
    assert len(changes.new) == 0
    assert len(changes.deleted) == 0
    store.close()


# ---------------------------------------------------------------------------
# 7. detect_changes with deleted file (in DB but not on disk)
# ---------------------------------------------------------------------------


def test_detect_changes_deleted(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _make_file(root, "a.py", "print('a')\n")

    store = _make_graph_store(tmp_path)

    file_hash = compute_file_hash(root / "a.py")
    # Insert nodes for a.py (still on disk) and gone.py (not on disk)
    store.upsert_nodes(
        [
            {
                "kind": "file",
                "name": "a.py",
                "qualified_name": "file::a.py",
                "file_path": "a.py",
                "content_hash": file_hash,
            },
            {
                "kind": "file",
                "name": "gone.py",
                "qualified_name": "file::gone.py",
                "file_path": "gone.py",
                "content_hash": "somehash",
            },
        ]
    )

    changes = detect_changes(root, store)

    assert Path("gone.py") in changes.deleted
    assert len(changes.new) == 0
    assert len(changes.modified) == 0
    store.close()


# ---------------------------------------------------------------------------
# 8. Non-git repo: falls back to hash comparison without error
# ---------------------------------------------------------------------------


def test_detect_changes_non_git_repo(tmp_path: Path) -> None:
    root = tmp_path / "not_a_repo"
    root.mkdir()
    _make_file(root, "main.py", "x = 1\n")

    store = _make_graph_store(tmp_path)

    # Should not raise; falls back to hash comparison
    changes = detect_changes(root, store)

    assert len(changes.new) == 1
    assert Path("main.py") in changes.new
    store.close()


# ---------------------------------------------------------------------------
# 9. compute_file_hash returns consistent results
# ---------------------------------------------------------------------------


def test_compute_file_hash_consistent(tmp_path: Path) -> None:
    f = tmp_path / "sample.txt"
    f.write_text("hello world\n", encoding="utf-8")

    h1 = compute_file_hash(f)
    h2 = compute_file_hash(f)

    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64  # SHA256 hex length


# ---------------------------------------------------------------------------
# 10. Symlinks are not followed
# ---------------------------------------------------------------------------


def test_symlinks_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    _make_file(root, "real.py", "x = 1\n")

    # Create a symlink to a directory that would contain .py files
    target_dir = tmp_path / "external"
    target_dir.mkdir()
    _make_file(target_dir, "secret.py", "y = 2\n")

    symlink_path = root / "linked"
    try:
        symlink_path.symlink_to(target_dir)
    except OSError:
        pytest.skip("Cannot create symlinks on this platform")

    # Also create a file symlink
    file_link = root / "alias.py"
    try:
        file_link.symlink_to(target_dir / "secret.py")
    except OSError:
        pytest.skip("Cannot create symlinks on this platform")

    found = discover_files(root)
    names = [str(p) for p in found]

    assert "real.py" in names
    # Symlinked dir/file should NOT appear
    assert not any("linked" in n for n in names)
    assert "alias.py" not in names
