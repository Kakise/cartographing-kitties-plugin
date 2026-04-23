"""Tests for storage path resolution helpers."""

from __future__ import annotations

from pathlib import Path

from cartograph.compat import derive_project_storage_dir, resolve_db_dir, resolve_storage_paths


class TestResolveStoragePaths:
    def test_default_layout_uses_local_pawprints_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("KITTY_STORAGE_ROOT", raising=False)
        monkeypatch.delenv("CARTOGRAPH_STORAGE_ROOT", raising=False)

        paths = resolve_storage_paths(tmp_path)

        assert paths.project_root == tmp_path.resolve()
        assert paths.storage_root == tmp_path.resolve()
        assert paths.data_dir == tmp_path.resolve() / ".pawprints"
        assert paths.db_path == paths.data_dir / "graph.db"
        assert paths.data_dir.exists()

    def test_centralized_layout_uses_project_specific_directory(self, tmp_path: Path):
        project_root = tmp_path / "project"
        storage_root = tmp_path / "storage"
        project_root.mkdir()

        paths = resolve_storage_paths(project_root, storage_root=storage_root)

        assert paths.project_root == project_root.resolve()
        assert paths.storage_root == storage_root.resolve()
        assert paths.data_dir.parent == storage_root.resolve()
        assert paths.data_dir.name.startswith("project-")
        assert paths.db_path == paths.data_dir / "graph.db"
        assert paths.data_dir.exists()

    def test_same_basename_different_roots_get_distinct_storage_dirs(self, tmp_path: Path):
        project_one = tmp_path / "one" / "sample_project"
        project_two = tmp_path / "two" / "sample_project"
        storage_root = tmp_path / "storage"
        project_one.mkdir(parents=True)
        project_two.mkdir(parents=True)

        first = derive_project_storage_dir(project_one, storage_root)
        second = derive_project_storage_dir(project_two, storage_root)

        assert first != second
        assert first.name.startswith("sample-project-")
        assert second.name.startswith("sample-project-")

    def test_moving_project_changes_storage_identity(self, tmp_path: Path):
        original = tmp_path / "old-parent" / "sample_project"
        moved = tmp_path / "new-parent" / "sample_project"
        storage_root = tmp_path / "storage"
        original.mkdir(parents=True)
        moved.mkdir(parents=True)

        original_paths = resolve_storage_paths(original, storage_root=storage_root)
        moved_paths = resolve_storage_paths(moved, storage_root=storage_root)

        assert original_paths.data_dir != moved_paths.data_dir

    def test_project_root_prefers_environment(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("KITTY_PROJECT_ROOT", str(tmp_path))

        paths = resolve_storage_paths()

        assert paths.project_root == tmp_path.resolve()

    def test_storage_root_falls_back_to_legacy_env(self, tmp_path: Path, monkeypatch):
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.delenv("KITTY_STORAGE_ROOT", raising=False)
        monkeypatch.setenv("CARTOGRAPH_STORAGE_ROOT", str(tmp_path / "central"))

        paths = resolve_storage_paths(project_root)

        assert paths.storage_root == (tmp_path / "central").resolve()

    def test_local_layout_renames_legacy_cartograph_dir(self, tmp_path: Path):
        legacy_dir = tmp_path / ".cartograph"
        legacy_dir.mkdir()

        paths = resolve_storage_paths(tmp_path)

        assert not legacy_dir.exists()
        assert paths.data_dir == tmp_path / ".pawprints"
        assert paths.data_dir.exists()

    def test_local_layout_reuses_existing_pawprints_dir(self, tmp_path: Path):
        data_dir = tmp_path / ".pawprints"
        data_dir.mkdir()

        paths = resolve_storage_paths(tmp_path)

        assert paths.data_dir == data_dir

    def test_resolve_db_dir_wraps_storage_paths(self, tmp_path: Path):
        assert resolve_db_dir(tmp_path) == (tmp_path / ".pawprints")

    def test_blank_project_name_falls_back_to_project_slug(self, tmp_path: Path):
        project_root = tmp_path / "---"
        storage_root = tmp_path / "storage"
        project_root.mkdir()

        derived = derive_project_storage_dir(project_root, storage_root)

        assert derived.name.startswith("project-")
