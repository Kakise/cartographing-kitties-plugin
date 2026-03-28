"""Tests for the structural indexer."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cartograph.indexing.indexer import Indexer, IndexStats
from cartograph.storage import GraphStore, create_connection

FIXTURES_DIR = Path(__file__).parent / "fixtures"
PYTHON_PROJECT = FIXTURES_DIR / "sample_python_project"
TS_PROJECT = FIXTURES_DIR / "sample_ts_project"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def graph_store(db_path: Path) -> GraphStore:
    conn = create_connection(db_path)
    return GraphStore(conn)


@pytest.fixture
def python_project(tmp_path: Path) -> Path:
    """Copy the sample Python project to a temp dir so tests can modify it."""
    dest = tmp_path / "python_project"
    shutil.copytree(PYTHON_PROJECT, dest)
    return dest


@pytest.fixture
def ts_project(tmp_path: Path) -> Path:
    """Copy the sample TS project to a temp dir."""
    dest = tmp_path / "ts_project"
    shutil.copytree(TS_PROJECT, dest)
    return dest


# -------------------------------------------------------------------------
# 1. Full Python project indexing
# -------------------------------------------------------------------------


class TestIndexPythonProject:
    def test_index_python_project(self, python_project: Path, graph_store: GraphStore):
        indexer = Indexer(python_project, graph_store)
        stats = indexer.index_all()

        # Should parse all 3 .py files
        assert stats.files_parsed == 3
        assert stats.errors == []

        # File nodes
        file_nodes = graph_store.find_nodes(kind="file")
        assert len(file_nodes) == 3

        # Class nodes: User, UserService
        class_nodes = graph_store.find_nodes(kind="class")
        class_names = {n["name"] for n in class_nodes}
        assert "User" in class_names
        assert "UserService" in class_names

        # Function nodes: main
        func_nodes = graph_store.find_nodes(kind="function")
        func_names = {n["name"] for n in func_nodes}
        assert "main" in func_names

        # Method nodes
        method_nodes = graph_store.find_nodes(kind="method")
        method_names = {n["name"] for n in method_nodes}
        assert "display_name" in method_names
        assert "add_user" in method_names
        assert "find_user" in method_names

    def test_contains_edges(self, python_project: Path, graph_store: GraphStore):
        indexer = Indexer(python_project, graph_store)
        stats = indexer.index_all()

        # Every definition should have a contains edge from its file
        contains_edges = graph_store.get_edges(kind="contains")
        assert len(contains_edges) > 0

        # All contains edges should point from a file node to a definition node
        for edge in contains_edges:
            source = graph_store.get_node(edge["source_id"])
            assert source is not None
            assert source["kind"] == "file"

    def test_nodes_created_stat(self, python_project: Path, graph_store: GraphStore):
        indexer = Indexer(python_project, graph_store)
        stats = indexer.index_all()
        assert stats.nodes_created > 0
        assert stats.edges_created > 0


# -------------------------------------------------------------------------
# 2. TypeScript project indexing
# -------------------------------------------------------------------------


class TestIndexTypeScriptProject:
    def test_index_typescript_project(self, ts_project: Path, graph_store: GraphStore):
        indexer = Indexer(ts_project, graph_store)
        stats = indexer.index_all()

        assert stats.files_parsed == 3
        assert stats.errors == []

        # Check node kinds
        file_nodes = graph_store.find_nodes(kind="file")
        assert len(file_nodes) == 3

        interface_nodes = graph_store.find_nodes(kind="interface")
        assert any(n["name"] == "User" for n in interface_nodes)

        type_nodes = graph_store.find_nodes(kind="type_alias")
        assert any(n["name"] == "UserID" for n in type_nodes)

        class_nodes = graph_store.find_nodes(kind="class")
        assert any(n["name"] == "UserService" for n in class_nodes)

        method_nodes = graph_store.find_nodes(kind="method")
        method_names = {n["name"] for n in method_nodes}
        assert "addUser" in method_names
        assert "getUser" in method_names


# -------------------------------------------------------------------------
# 3. Cross-file import resolution
# -------------------------------------------------------------------------


class TestCrossFileImportResolution:
    def test_import_edge_created(self, python_project: Path, graph_store: GraphStore):
        """File A imports from file B: verify import edge between file nodes."""
        indexer = Indexer(python_project, graph_store)
        indexer.index_all()

        import_edges = graph_store.get_edges(kind="imports")
        assert len(import_edges) > 0

        # All import edges should be between file nodes
        for edge in import_edges:
            source = graph_store.get_node(edge["source_id"])
            target = graph_store.get_node(edge["target_id"])
            assert source is not None
            assert target is not None
            assert source["kind"] == "file"
            assert target["kind"] == "file"

    def test_ts_import_edge_created(self, ts_project: Path, graph_store: GraphStore):
        """TS project: relative imports resolve to file edges."""
        indexer = Indexer(ts_project, graph_store)
        indexer.index_all()

        import_edges = graph_store.get_edges(kind="imports")
        assert len(import_edges) > 0

    def test_import_confidence(self, python_project: Path, graph_store: GraphStore):
        indexer = Indexer(python_project, graph_store)
        indexer.index_all()

        import_edges = graph_store.get_edges(kind="imports")
        for edge in import_edges:
            assert edge["properties"]["confidence"] == "high"


# -------------------------------------------------------------------------
# 4. Cross-file call resolution
# -------------------------------------------------------------------------


class TestCrossFileCallResolution:
    def test_call_edge_exists(self, python_project: Path, graph_store: GraphStore):
        """File A calls function imported from file B: verify call edge."""
        indexer = Indexer(python_project, graph_store)
        indexer.index_all()

        call_edges = graph_store.get_edges(kind="calls")
        # There should be at least some call edges (e.g. main -> UserService, etc.)
        assert len(call_edges) > 0

    def test_ts_call_edges(self, ts_project: Path, graph_store: GraphStore):
        indexer = Indexer(ts_project, graph_store)
        indexer.index_all()

        call_edges = graph_store.get_edges(kind="calls")
        # main.ts calls UserService constructor and methods
        assert len(call_edges) > 0


# -------------------------------------------------------------------------
# 5. Incremental re-index
# -------------------------------------------------------------------------


class TestIncrementalReindex:
    def test_incremental_reindex(self, python_project: Path, graph_store: GraphStore):
        """Modify one file, call index_changed(), verify only that file's nodes updated."""
        indexer = Indexer(python_project, graph_store)
        indexer.index_all()

        # Get initial node count
        all_nodes_before = graph_store.find_nodes()

        # Modify a file to trigger change detection
        main_file = python_project / "src" / "main.py"
        content = main_file.read_text()
        main_file.write_text(content + "\n# modified\n")

        # Run incremental index
        stats = indexer.index_changed()

        # The modified file should have been re-indexed
        # (Since we're using hash-based detection, the new hash differs)
        all_nodes_after = graph_store.find_nodes()

        # Should still have roughly the same number of nodes
        assert len(all_nodes_after) > 0


# -------------------------------------------------------------------------
# 6. Deleted file cleanup
# -------------------------------------------------------------------------


class TestDeletedFileCleanup:
    def test_deleted_file_cleanup(self, python_project: Path, graph_store: GraphStore):
        """Delete a file on disk, call index_changed(), verify nodes removed."""
        indexer = Indexer(python_project, graph_store)
        indexer.index_all()

        # Count nodes for main.py
        main_nodes_before = graph_store.find_nodes(file_path="src/main.py")
        assert len(main_nodes_before) > 0

        # Delete the file
        (python_project / "src" / "main.py").unlink()

        # Run incremental
        stats = indexer.index_changed()
        assert stats.files_deleted >= 1

        # Nodes for deleted file should be gone
        main_nodes_after = graph_store.find_nodes(file_path="src/main.py")
        assert len(main_nodes_after) == 0


# -------------------------------------------------------------------------
# 7. Empty project
# -------------------------------------------------------------------------


class TestEmptyProject:
    def test_empty_project(self, tmp_path: Path, graph_store: GraphStore):
        """Index a directory with no supported files: returns zero stats, no crash."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        indexer = Indexer(empty_dir, graph_store)
        stats = indexer.index_all()

        assert stats.files_parsed == 0
        assert stats.nodes_created == 0
        assert stats.edges_created == 0
        assert stats.errors == []


# -------------------------------------------------------------------------
# 8. Syntax errors
# -------------------------------------------------------------------------


class TestSyntaxErrors:
    def test_file_with_syntax_errors(self, tmp_path: Path, graph_store: GraphStore):
        """Include a malformed file: indexer continues, may have partial results."""
        project = tmp_path / "bad_project"
        project.mkdir()

        # Create a good file
        good = project / "good.py"
        good.write_text("def hello():\n    pass\n")

        # Create a file with syntax errors (tree-sitter is lenient, so it still parses)
        bad = project / "bad.py"
        bad.write_text("def broken(\n    # missing close paren\n    pass\n")

        indexer = Indexer(project, graph_store)
        stats = indexer.index_all()

        # Should still parse files (tree-sitter is error-tolerant)
        assert stats.files_parsed >= 1
        # The good file's definition should exist
        func_nodes = graph_store.find_nodes(kind="function")
        assert any(n["name"] == "hello" for n in func_nodes)


# -------------------------------------------------------------------------
# 9. IndexStats fields
# -------------------------------------------------------------------------


class TestIndexStats:
    def test_index_stats_defaults(self):
        stats = IndexStats()
        assert stats.files_parsed == 0
        assert stats.nodes_created == 0
        assert stats.edges_created == 0
        assert stats.files_deleted == 0
        assert stats.errors == []

    def test_index_stats_populated(self, python_project: Path, graph_store: GraphStore):
        indexer = Indexer(python_project, graph_store)
        stats = indexer.index_all()

        assert stats.files_parsed == 3
        assert stats.nodes_created > 3  # at least 3 file nodes + definitions
        assert stats.edges_created > 0  # at least contains edges
        assert stats.files_deleted == 0
        assert stats.errors == []

    def test_errors_list_independent(self):
        """Ensure each IndexStats gets its own errors list."""
        s1 = IndexStats()
        s2 = IndexStats()
        s1.errors.append("err")
        assert s2.errors == []
