"""Direct coverage tests for package and server entry points."""

from __future__ import annotations

import importlib.util
import runpy
import sys
from pathlib import Path

import pytest

import cartograph
import cartograph.server.main as server_main
import cartograph.web.main as web_main
from cartograph.compat import resolve_storage_paths
from cartograph.storage.connection import create_connection

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"


class TestPackageEntrypoints:
    def test_main_runs_mcp_stdio_transport(self, monkeypatch):
        called: list[str] = []

        monkeypatch.setattr(server_main.mcp, "run", lambda transport: called.append(transport))

        cartograph.main()

        assert called == ["stdio"]

    def test_version_falls_back_when_package_metadata_missing(self, monkeypatch):
        source_path = Path(cartograph.__file__)
        monkeypatch.setattr(
            "importlib.metadata.version",
            lambda name: (_ for _ in ()).throw(cartograph.PackageNotFoundError()),
        )

        spec = importlib.util.spec_from_file_location("cartograph_test_fallback", source_path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.__version__ == "0.0.0-dev"

    def test_serve_uses_centralized_storage_root(self, tmp_path: Path, monkeypatch):
        project_root = tmp_path / "project"
        storage_root = tmp_path / "storage"
        project_root.mkdir()
        paths = resolve_storage_paths(project_root, storage_root=storage_root)
        conn = create_connection(paths.db_path, check_same_thread=False)

        captured: list[tuple[object, int]] = []

        def fake_run_server(store, port):
            captured.append((store, port))

        monkeypatch.setattr("cartograph.web.server.run_server", fake_run_server)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "kitty-graph",
                "--project-root",
                str(project_root),
                "--storage-root",
                str(storage_root),
                "--port",
                "4040",
            ],
        )

        try:
            cartograph.serve()
        finally:
            conn.close()

        assert captured
        assert captured[0][1] == 4040

    def test_serve_exits_when_db_missing(self, tmp_path: Path, monkeypatch, capsys):
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "kitty-graph",
                "--project-root",
                str(project_root),
            ],
        )

        with pytest.raises(SystemExit) as excinfo:
            cartograph.serve()

        assert excinfo.value.code == 1
        assert "No graph database found" in capsys.readouterr().err


class TestWebMainEntrypoint:
    def test_web_main_serve_runs_server_with_existing_db(self, tmp_path: Path, monkeypatch):
        project_root = tmp_path / "project"
        storage_root = tmp_path / "storage"
        project_root.mkdir()
        paths = resolve_storage_paths(project_root, storage_root=storage_root)
        conn = create_connection(paths.db_path, check_same_thread=False)

        captured: list[tuple[object, int]] = []

        def fake_run_server(store, port):
            captured.append((store, port))

        monkeypatch.setattr("cartograph.web.server.run_server", fake_run_server)

        try:
            web_main.serve(port=5050, project_root=str(project_root), storage_root=str(storage_root))
        finally:
            conn.close()

        assert captured
        assert captured[0][1] == 5050

    def test_web_main_serve_exits_when_db_missing(self, tmp_path: Path):
        project_root = tmp_path / "project"
        project_root.mkdir()

        with pytest.raises(SystemExit) as excinfo:
            web_main.serve(project_root=str(project_root))

        assert excinfo.value.code == 1


class TestServerMainLifespan:
    @pytest.mark.anyio
    async def test_lifespan_sets_and_clears_global_state(self, tmp_path: Path, monkeypatch):
        paths = resolve_storage_paths(tmp_path / "project", storage_root=tmp_path / "storage")
        monkeypatch.setattr(server_main, "resolve_storage_paths", lambda: paths)

        async with server_main.lifespan(server_main.mcp):
            assert server_main._store is not None
            assert server_main._root == paths.project_root
            assert server_main._storage_paths == paths

        assert server_main._store is None
        assert server_main._root is None
        assert server_main._storage_paths is None

    def test_module_run_as_main_aliases_and_starts_stdio(self, monkeypatch):
        original_module = sys.modules.get("cartograph.server.main")
        original_main = sys.modules.get("__main__")
        fake_calls: list[str] = []

        from mcp.server.fastmcp import FastMCP

        monkeypatch.setattr(FastMCP, "run", lambda self, transport: fake_calls.append(transport))
        sys.modules.pop("cartograph.server.main", None)

        try:
            runpy.run_path(str(Path(server_main.__file__)), run_name="__main__")
            assert fake_calls == ["stdio"]
            assert "cartograph.server.main" in sys.modules
        finally:
            if original_module is not None:
                sys.modules["cartograph.server.main"] = original_module
            else:
                sys.modules.pop("cartograph.server.main", None)
            if original_main is not None:
                sys.modules["__main__"] = original_main
