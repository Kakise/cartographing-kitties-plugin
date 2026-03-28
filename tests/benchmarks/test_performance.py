"""Dedicated performance benchmarks for Cartograph.

These tests are marked with @pytest.mark.slow so they can be skipped
during normal test runs with: pytest -m "not slow"
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from cartograph.indexing.indexer import Indexer
from cartograph.storage import GraphStore, create_connection

BENCHMARK_PROJECT = Path(__file__).parent.parent / "fixtures" / "benchmark_project"


@pytest.fixture
def benchmark_project(tmp_path: Path) -> Path:
    """Copy the benchmark project to a temp dir."""
    dest = tmp_path / "benchmark_project"
    shutil.copytree(BENCHMARK_PROJECT, dest)
    return dest


@pytest.fixture
def graph_store(tmp_path: Path) -> GraphStore:
    db_path = tmp_path / "bench.db"
    conn = create_connection(db_path)
    store = GraphStore(conn)
    yield store
    store.close()


@pytest.fixture
def indexed_store(benchmark_project: Path, graph_store: GraphStore):
    """Pre-index the benchmark project."""
    indexer = Indexer(benchmark_project, graph_store)
    stats = indexer.index_all()
    return graph_store, indexer, stats


@pytest.mark.slow
class TestIndexingPerformance:
    def test_full_index_under_10_seconds(self, benchmark_project: Path, tmp_path: Path):
        """Full index of ~30 file benchmark project completes in < 10s."""
        db_path = tmp_path / "perf.db"
        conn = create_connection(db_path)
        store = GraphStore(conn)

        start = time.perf_counter()
        indexer = Indexer(benchmark_project, store)
        stats = indexer.index_all()
        elapsed = time.perf_counter() - start

        store.close()
        assert elapsed < 10.0, f"Full index took {elapsed:.2f}s, expected < 10s"
        assert stats.files_parsed > 0

    def test_incremental_reindex_under_3_seconds(
        self, benchmark_project: Path, graph_store: GraphStore
    ):
        """Incremental re-index after modifying 5 files completes in < 3s."""
        indexer = Indexer(benchmark_project, graph_store)
        indexer.index_all()

        # Modify 5 files to trigger re-indexing
        files_to_modify = list(benchmark_project.rglob("*.py"))[:5]
        for f in files_to_modify:
            content = f.read_text()
            f.write_text(content + "\n# modified for benchmark\n")

        start = time.perf_counter()
        stats = indexer.index_changed()
        elapsed = time.perf_counter() - start

        assert elapsed < 3.0, f"Incremental re-index took {elapsed:.2f}s, expected < 3s"


@pytest.mark.slow
class TestQueryPerformance:
    def test_single_query_under_100ms(self, indexed_store):
        """A single find_nodes query completes in < 100ms."""
        store, _, _ = indexed_store

        start = time.perf_counter()
        results = store.find_nodes(name="User")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Query took {elapsed * 1000:.1f}ms, expected < 100ms"
        assert len(results) > 0

    def test_fts_search_under_100ms(self, indexed_store):
        """FTS5 search completes in < 100ms."""
        store, _, _ = indexed_store

        start = time.perf_counter()
        results = store.search("user")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"FTS search took {elapsed * 1000:.1f}ms, expected < 100ms"
        assert len(results) > 0

    def test_traversal_under_100ms(self, indexed_store):
        """Reverse dependency traversal completes in < 100ms."""
        store, _, _ = indexed_store

        # Find a node that should have dependents
        user_nodes = store.find_nodes(name="User")
        assert len(user_nodes) > 0
        node_id = user_nodes[0]["id"]

        start = time.perf_counter()
        dependents = store.reverse_dependencies(node_id, max_depth=5)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Traversal took {elapsed * 1000:.1f}ms, expected < 100ms"
