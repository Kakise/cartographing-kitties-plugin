"""Tests for the annotation data-gathering and submission helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cartograph.annotation import (
    AnnotationResult,
    NodeContext,
    extract_source,
    get_pending_nodes,
    normalize_tags,
    write_annotations,
)
from cartograph.storage import GraphStore, create_connection

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _insert_nodes(
    store: GraphStore,
    count: int,
    *,
    status: str = "pending",
    file_path: str = "test.py",
    prefix: str = "node",
) -> list[int]:
    """Insert *count* test nodes into *store* and return their IDs."""
    nodes = [
        {
            "kind": "function",
            "name": f"{prefix}_{i}",
            "qualified_name": f"mod.{prefix}_{i}",
            "file_path": file_path,
            "start_line": 1,
            "end_line": 3,
            "language": "python",
            "annotation_status": status,
        }
        for i in range(count)
    ]
    return store.upsert_nodes(nodes)


def _insert_nodes_with_edges(
    store: GraphStore,
    count: int,
    *,
    status: str = "pending",
    file_path: str = "test.py",
    prefix: str = "node",
) -> list[int]:
    """Insert test nodes with edges between them."""
    ids = _insert_nodes(store, count, status=status, file_path=file_path, prefix=prefix)
    # Create edges between consecutive nodes.
    for i in range(len(ids) - 1):
        store.upsert_edges(
            [
                {
                    "source_id": ids[i],
                    "target_id": ids[i + 1],
                    "kind": "calls",
                }
            ]
        )
    return ids


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def store(db_path: Path) -> GraphStore:
    conn = create_connection(db_path)
    return GraphStore(conn)


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    """Create a small Python source file."""
    p = tmp_path / "test.py"
    p.write_text(
        'def hello():\n    """Say hello."""\n    return "hello"\n',
        encoding="utf-8",
    )
    return p


# ---------------------------------------------------------------------------
# Tests: get_pending_nodes
# ---------------------------------------------------------------------------


class TestGetPendingNodes:
    def test_returns_nodes_with_source_and_neighbors(
        self, store: GraphStore, source_file: Path
    ) -> None:
        """Pending nodes are returned with source code and neighbor info."""
        ids = _insert_nodes_with_edges(store, 3, file_path=str(source_file), prefix="pending")

        result = get_pending_nodes(store, batch_size=10, source_root=source_file.parent)

        assert len(result) == 3
        for ctx in result:
            assert isinstance(ctx, NodeContext)
            assert ctx.kind == "function"
            assert ctx.source != "(source unavailable)"
            assert ctx.source.startswith("def hello()")

    def test_neighbors_populated(self, store: GraphStore, source_file: Path) -> None:
        """Nodes with edges have neighbors populated."""
        ids = _insert_nodes_with_edges(store, 3, file_path=str(source_file), prefix="nbr")

        result = get_pending_nodes(store, batch_size=10, source_root=source_file.parent)

        # Each middle node should have both incoming and outgoing neighbors.
        all_neighbors = []
        for ctx in result:
            all_neighbors.extend(ctx.neighbors)
        # We created 2 edges (0->1, 1->2), so at least some neighbors.
        assert len(all_neighbors) > 0
        # Check neighbor dict structure.
        for nbr in all_neighbors:
            assert "direction" in nbr
            assert "edge_kind" in nbr
            assert "kind" in nbr
            assert "qualified_name" in nbr

    def test_returns_empty_for_empty_store(self, store: GraphStore) -> None:
        """Empty store returns an empty list."""
        result = get_pending_nodes(store)
        assert result == []

    def test_respects_batch_size(self, store: GraphStore, source_file: Path) -> None:
        """Only batch_size nodes are returned."""
        _insert_nodes(store, 20, file_path=str(source_file))
        result = get_pending_nodes(store, batch_size=5)
        assert len(result) == 5

    def test_skips_annotated_nodes(self, store: GraphStore, source_file: Path) -> None:
        """Annotated nodes are not returned."""
        _insert_nodes(store, 3, status="annotated", file_path=str(source_file))
        result = get_pending_nodes(store)
        assert result == []

    def test_includes_failed_when_retry(self, store: GraphStore, source_file: Path) -> None:
        """Failed nodes are included when retry_failed=True."""
        _insert_nodes(store, 2, status="failed", file_path=str(source_file), prefix="fail")
        _insert_nodes(store, 1, status="pending", file_path=str(source_file), prefix="pend")

        result_no_retry = get_pending_nodes(store, retry_failed=False)
        assert len(result_no_retry) == 1

        result_with_retry = get_pending_nodes(store, retry_failed=True)
        assert len(result_with_retry) == 3


# ---------------------------------------------------------------------------
# Tests: write_annotations
# ---------------------------------------------------------------------------


class TestWriteAnnotations:
    def test_persists_summaries_tags_roles(self, store: GraphStore, source_file: Path) -> None:
        """write_annotations persists summary, normalized tags, and role."""
        _insert_nodes(store, 2, file_path=str(source_file), prefix="wr")

        results = [
            AnnotationResult(
                qualified_name="mod.wr_0",
                summary="Handles user auth",
                tags=["auth", "middleware"],
                role="Auth middleware",
            ),
            AnnotationResult(
                qualified_name="mod.wr_1",
                summary="Validates input",
                tags=["validation"],
                role="Validator",
            ),
        ]

        stats = write_annotations(store, results)

        assert stats.written == 2
        assert stats.failed == 0
        assert stats.skipped == 0

        node0 = store.get_node_by_name("mod.wr_0")
        assert node0 is not None
        assert node0["annotation_status"] == "annotated"
        assert node0["summary"] == "Handles user auth"
        props = node0["properties"]
        if isinstance(props, str):
            props = json.loads(props)
        assert props["tags"] == ["auth", "middleware"]
        assert props["role"] == "Auth middleware"

    def test_empty_results_is_noop(self, store: GraphStore) -> None:
        """Empty results list returns zero stats."""
        stats = write_annotations(store, [])
        assert stats.written == 0
        assert stats.failed == 0
        assert stats.skipped == 0

    def test_marks_failed(self, store: GraphStore, source_file: Path) -> None:
        """Results with failed=True mark the node as failed."""
        _insert_nodes(store, 2, file_path=str(source_file), prefix="failwr")

        results = [
            AnnotationResult(qualified_name="mod.failwr_0", failed=True),
            AnnotationResult(
                qualified_name="mod.failwr_1",
                summary="OK",
                tags=["utilities"],
                role="helper",
            ),
        ]

        stats = write_annotations(store, results)

        assert stats.written == 1
        assert stats.failed == 1

        node0 = store.get_node_by_name("mod.failwr_0")
        assert node0 is not None
        assert node0["annotation_status"] == "failed"

        node1 = store.get_node_by_name("mod.failwr_1")
        assert node1 is not None
        assert node1["annotation_status"] == "annotated"

    def test_skips_unknown_qualified_name(self, store: GraphStore, source_file: Path) -> None:
        """Results with unknown qualified_name are skipped."""
        _insert_nodes(store, 1, file_path=str(source_file), prefix="known")

        results = [
            AnnotationResult(
                qualified_name="mod.known_0",
                summary="OK",
                tags=["utilities"],
            ),
            AnnotationResult(
                qualified_name="mod.nonexistent",
                summary="Ghost",
                tags=["unknown"],
            ),
        ]

        stats = write_annotations(store, results)

        assert stats.written == 1
        assert stats.skipped == 1


# ---------------------------------------------------------------------------
# Tests: normalize_tags
# ---------------------------------------------------------------------------


class TestNormalizeTags:
    def test_maps_synonyms_to_canonical(self) -> None:
        """Tags are lowercased and synonyms mapped to seed taxonomy."""
        tags = normalize_tags(["Authentication", "DB", "Utils", "TESTING", "auth"])
        # "Authentication" -> "auth", "DB" -> "database",
        # "Utils" -> "utilities", "TESTING" -> "testing"
        # "auth" is a duplicate after synonym resolution
        assert tags == ["auth", "database", "utilities", "testing"]

    def test_preserves_unknown_tags(self) -> None:
        """Tags not in synonym map are kept as-is (lowercased)."""
        tags = normalize_tags(["Custom", "Payment"])
        assert tags == ["custom", "payment"]

    def test_deduplicates(self) -> None:
        """Duplicate tags after normalization are removed."""
        tags = normalize_tags(["auth", "authentication", "Authorization"])
        assert tags == ["auth"]

    def test_empty_input(self) -> None:
        """Empty input returns empty list."""
        assert normalize_tags([]) == []

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        tags = normalize_tags(["  auth  ", " database "])
        assert tags == ["auth", "database"]

    def test_skips_non_string_tags(self) -> None:
        """Non-string elements are silently skipped."""
        tags = normalize_tags(["auth", 42, None, True, "database"])
        assert tags == ["auth", "database"]


# ---------------------------------------------------------------------------
# Tests: extract_source
# ---------------------------------------------------------------------------


class TestExtractSource:
    def test_returns_source_for_valid_file(self, source_file: Path) -> None:
        """Source code is extracted from a valid file."""
        source = extract_source(
            file_path=str(source_file),
            start_line=1,
            end_line=3,
        )
        assert source.startswith("def hello()")
        assert "return" in source

    def test_returns_unavailable_for_missing_file(self) -> None:
        """Missing files return '(source unavailable)'."""
        source = extract_source(
            file_path="/nonexistent/path/file.py",
            start_line=1,
            end_line=3,
        )
        assert source == "(source unavailable)"

    def test_returns_unavailable_for_empty_path(self) -> None:
        """Empty file path returns '(source unavailable)'."""
        source = extract_source(
            file_path="",
            start_line=1,
            end_line=3,
        )
        assert source == "(source unavailable)"

    def test_returns_whole_file_without_lines(self, source_file: Path) -> None:
        """Without line range, returns entire file content."""
        source = extract_source(
            file_path=str(source_file),
            start_line=None,
            end_line=None,
        )
        assert "def hello()" in source
        assert 'return "hello"' in source

    def test_resolves_relative_path(self, source_file: Path) -> None:
        """Relative paths are resolved against source_root."""
        source = extract_source(
            file_path="test.py",
            start_line=1,
            end_line=3,
            source_root=source_file.parent,
        )
        assert source.startswith("def hello()")
