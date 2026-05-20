"""Mixed-language integration test: Rust + C++ + Python in a single index."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cartograph.indexing.indexer import Indexer
from cartograph.storage import GraphStore, create_connection

FIXTURES_DIR = Path(__file__).parent / "fixtures"
POLYGLOT_PROJECT = FIXTURES_DIR / "polyglot_rust_cpp"


@pytest.fixture
def graph_store(tmp_path: Path) -> GraphStore:
    conn = create_connection(tmp_path / "test.db")
    return GraphStore(conn)


@pytest.fixture
def polyglot_project(tmp_path: Path) -> Path:
    dest = tmp_path / "polyglot"
    shutil.copytree(POLYGLOT_PROJECT, dest)
    return dest


class TestPolyglotIndexing:
    def test_all_languages_contribute_nodes(self, polyglot_project: Path, graph_store: GraphStore):
        indexer = Indexer(polyglot_project, graph_store)
        stats = indexer.index_all()
        assert stats.errors == []
        assert stats.files_parsed >= 5  # 1 Rust + 4 C++ (h/cpp/h/cpp incl empty.h) + 1 Python

        file_nodes = graph_store.find_nodes(kind="file")
        languages = {n["language"] for n in file_nodes if n.get("language")}
        assert {"rust", "cpp", "python"}.issubset(languages)

    def test_unsupported_extension_silently_skipped(
        self, polyglot_project: Path, graph_store: GraphStore
    ):
        indexer = Indexer(polyglot_project, graph_store)
        stats = indexer.index_all()
        assert stats.errors == []
        file_nodes = graph_store.find_nodes(kind="file")
        names = {n["name"] for n in file_nodes}
        assert "notes.zig" not in names

    def test_empty_header_does_not_error(self, polyglot_project: Path, graph_store: GraphStore):
        indexer = Indexer(polyglot_project, graph_store)
        stats = indexer.index_all()
        assert stats.errors == []
        file_nodes = graph_store.find_nodes(kind="file")
        names = {n["name"] for n in file_nodes}
        assert "empty.h" in names

    def test_rank_nodes_returns_multilingual(self, polyglot_project: Path, graph_store: GraphStore):
        indexer = Indexer(polyglot_project, graph_store)
        indexer.index_all()
        # At minimum, the index must contain nodes from at least two new languages.
        class_nodes = graph_store.find_nodes(kind="class")
        class_langs = {n["language"] for n in class_nodes if n.get("language")}
        assert {"rust", "cpp"}.issubset(class_langs)
