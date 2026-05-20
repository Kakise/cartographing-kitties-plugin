"""End-to-end indexing tests for the C++ extractor + include resolver."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cartograph.indexing.indexer import Indexer
from cartograph.storage import GraphStore, create_connection

FIXTURES_DIR = Path(__file__).parent / "fixtures"
CPP_PROJECT = FIXTURES_DIR / "cpp_sample"


@pytest.fixture
def graph_store(tmp_path: Path) -> GraphStore:
    conn = create_connection(tmp_path / "test.db")
    return GraphStore(conn)


@pytest.fixture
def cpp_project(tmp_path: Path) -> Path:
    dest = tmp_path / "cpp_sample"
    shutil.copytree(CPP_PROJECT, dest)
    return dest


class TestCppIndexing:
    def test_indexes_cpp_files(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        stats = indexer.index_all()
        assert stats.errors == []
        # shape.h + circle.h + circle.cpp + main.cpp = 4 files
        assert stats.files_parsed == 4

    def test_class_nodes(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()
        classes = graph_store.find_nodes(kind="class")
        names = {n["name"] for n in classes}
        assert {"Shape", "Circle", "Triangle"}.issubset(names)

    def test_quoted_include_resolves(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()
        imports_edges = graph_store.get_edges(kind="imports")
        resolved_pairs = set()
        for edge in imports_edges:
            src = graph_store.get_node(edge["source_id"])
            tgt = graph_store.get_node(edge["target_id"])
            if not src or not tgt:
                continue
            if src["kind"] == "file" and tgt["kind"] == "file":
                resolved_pairs.add((src["name"], tgt["name"]))
        # main.cpp #include "circle.h" should resolve via the sibling include/ dir
        assert ("main.cpp", "circle.h") in resolved_pairs
        # circle.h #include "shape.h" — same-directory
        assert ("circle.h", "shape.h") in resolved_pairs

    def test_system_include_not_resolved(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()
        file_nodes = graph_store.find_nodes(kind="file")
        names = {n["name"] for n in file_nodes}
        # `<vector>` and `<iostream>` should not produce file nodes
        assert "vector" not in names
        assert "iostream" not in names

    def test_inheritance_edge(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()
        inherits = graph_store.get_edges(kind="inherits")
        # At least Circle → Shape
        pairs = set()
        for edge in inherits:
            src = graph_store.get_node(edge["source_id"])
            tgt = graph_store.get_node(edge["target_id"])
            if src and tgt:
                pairs.add((src["name"], tgt["name"]))
        assert ("Circle", "Shape") in pairs

    def test_out_of_line_method_linked_to_class(self, cpp_project: Path, graph_store: GraphStore):
        """Circle::area is defined in circle.cpp but Circle lives in circle.h.

        After indexing, the class node should `contains` the method node even
        though they live in different files.
        """
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()

        contains = graph_store.get_edges(kind="contains")
        method_linked = False
        for edge in contains:
            src = graph_store.get_node(edge["source_id"])
            tgt = graph_store.get_node(edge["target_id"])
            if not src or not tgt:
                continue
            if (
                src["kind"] == "class"
                and src["name"] == "Circle"
                and tgt["kind"] == "method"
                and tgt["name"] == "area"
            ):
                method_linked = True
                break
        assert method_linked, "expected class Circle → method area contains edge"

    def test_namespace_node(self, cpp_project: Path, graph_store: GraphStore):
        indexer = Indexer(cpp_project, graph_store)
        indexer.index_all()
        modules = graph_store.find_nodes(kind="module")
        names = {n["name"] for n in modules}
        assert "geo" in names

    def test_c_style_h_file_parses(self, tmp_path: Path, graph_store: GraphStore):
        """A pure-C header should parse without errors when mapped to the C++ grammar."""
        legacy = tmp_path / "legacy_project"
        legacy.mkdir()
        (legacy / "legacy.h").write_text("struct Foo { int x; };\nint helper(struct Foo f);\n")
        indexer = Indexer(legacy, graph_store)
        stats = indexer.index_all()
        assert stats.errors == []
        assert stats.files_parsed == 1
        classes = graph_store.find_nodes(kind="class")
        names = {n["name"] for n in classes}
        assert "Foo" in names
