"""End-to-end indexing tests for the Rust extractor + resolver."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cartograph.indexing.indexer import Indexer
from cartograph.storage import GraphStore, create_connection

FIXTURES_DIR = Path(__file__).parent / "fixtures"
RUST_PROJECT = FIXTURES_DIR / "rust_sample"


@pytest.fixture
def graph_store(tmp_path: Path) -> GraphStore:
    conn = create_connection(tmp_path / "test.db")
    return GraphStore(conn)


@pytest.fixture
def rust_project(tmp_path: Path) -> Path:
    dest = tmp_path / "rust_sample"
    shutil.copytree(RUST_PROJECT, dest)
    return dest


class TestRustIndexing:
    def test_indexes_rust_files(self, rust_project: Path, graph_store: GraphStore):
        indexer = Indexer(rust_project, graph_store)
        stats = indexer.index_all()

        assert stats.errors == []
        # main.rs + lib.rs + geometry/mod.rs + geometry/circle.rs = 4 files
        assert stats.files_parsed == 4

        file_nodes = graph_store.find_nodes(kind="file")
        assert len(file_nodes) == 4

    def test_extracts_struct_as_class(self, rust_project: Path, graph_store: GraphStore):
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        classes = graph_store.find_nodes(kind="class")
        class_names = {n["name"] for n in classes}
        assert "Circle" in class_names

    def test_extracts_trait_as_interface(self, rust_project: Path, graph_store: GraphStore):
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        interfaces = graph_store.find_nodes(kind="interface")
        names = {n["name"] for n in interfaces}
        assert "Shape" in names

    def test_extracts_impl_methods(self, rust_project: Path, graph_store: GraphStore):
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        methods = graph_store.find_nodes(kind="method")
        method_names = {n["name"] for n in methods}
        # Circle::new, Circle::area, Shape::area (trait signature)
        assert "new" in method_names
        assert "area" in method_names

    def test_inherits_edge_for_impl_trait_for_type(
        self, rust_project: Path, graph_store: GraphStore
    ):
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        inherits_edges = graph_store.get_edges(kind="inherits")
        assert inherits_edges, "expected at least one inherits edge for impl Shape for Circle"

        # Endpoints: Circle (class) → Shape (interface)
        for edge in inherits_edges:
            src = graph_store.get_node(edge["source_id"])
            tgt = graph_store.get_node(edge["target_id"])
            assert src is not None and tgt is not None
            if src["name"] == "Circle" and tgt["name"] == "Shape":
                break
        else:
            pytest.fail("no inherits edge Circle->Shape found")

    def test_use_crate_resolves_to_local_file(self, rust_project: Path, graph_store: GraphStore):
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        # `use crate::geometry::Circle;` in main.rs should produce an imports edge
        # from main.rs's file node to geometry/mod.rs's file node (the file containing
        # the `crate::geometry` module).
        imports_edges = graph_store.get_edges(kind="imports")
        resolved = []
        for edge in imports_edges:
            src = graph_store.get_node(edge["source_id"])
            tgt = graph_store.get_node(edge["target_id"])
            if not src or not tgt:
                continue
            if src["kind"] == "file" and tgt["kind"] == "file":
                resolved.append((src["name"], tgt["name"]))

        # Main file imports something from the geometry tree
        assert any(s == "main.rs" for s, _ in resolved), (
            f"expected main.rs to import a local file; resolved={resolved}"
        )

    def test_external_use_is_leaf(self, rust_project: Path, graph_store: GraphStore):
        """`use std::collections::HashMap;` should not produce a file→file imports edge."""
        indexer = Indexer(rust_project, graph_store)
        indexer.index_all()

        # No file node should be named "HashMap.rs" or "collections.rs" anywhere
        file_nodes = graph_store.find_nodes(kind="file")
        names = {n["name"] for n in file_nodes}
        assert "HashMap.rs" not in names
        assert "collections.rs" not in names
