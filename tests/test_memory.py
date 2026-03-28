"""Tests for the litter-box and treat-box memory system."""

from __future__ import annotations

from pathlib import Path

import pytest

from cartograph.memory import add_entry, export_markdown, query_entries
from cartograph.storage import GraphStore, create_connection

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAddAndQueryLitterBox:
    def test_add_and_query_litter_box(self, store: GraphStore) -> None:
        """Add a litter-box entry and query it back."""
        entry_id = add_entry(
            store,
            box="litter",
            category="failure",
            description="Timeout when calling external API without retry",
            context="src/api/client.py:42",
            source_agent="correctness-reviewer",
        )
        assert isinstance(entry_id, int)
        assert entry_id > 0

        entries = query_entries(store, box="litter")
        assert len(entries) == 1
        assert entries[0].id == entry_id
        assert entries[0].box == "litter"
        assert entries[0].category == "failure"
        assert entries[0].description == "Timeout when calling external API without retry"
        assert entries[0].context == "src/api/client.py:42"
        assert entries[0].source_agent == "correctness-reviewer"


class TestAddAndQueryTreatBox:
    def test_add_and_query_treat_box(self, store: GraphStore) -> None:
        """Add a treat-box entry and query it back."""
        entry_id = add_entry(
            store,
            box="treat",
            category="best-practice",
            description="Always use connection pooling for DB access",
            context="Validated in load tests",
            source_agent="pattern-analyst",
        )
        assert isinstance(entry_id, int)
        assert entry_id > 0

        entries = query_entries(store, box="treat")
        assert len(entries) == 1
        assert entries[0].id == entry_id
        assert entries[0].box == "treat"
        assert entries[0].category == "best-practice"
        assert entries[0].description == "Always use connection pooling for DB access"


class TestQueryByCategory:
    def test_query_by_category(self, store: GraphStore) -> None:
        """Add entries with different categories and filter by one."""
        add_entry(store, "litter", "failure", "Test failure 1")
        add_entry(store, "litter", "anti-pattern", "God object in service layer")
        add_entry(store, "litter", "failure", "Test failure 2")

        all_entries = query_entries(store, "litter")
        assert len(all_entries) == 3

        failures = query_entries(store, "litter", category="failure")
        assert len(failures) == 2
        assert all(e.category == "failure" for e in failures)

        anti_patterns = query_entries(store, "litter", category="anti-pattern")
        assert len(anti_patterns) == 1
        assert anti_patterns[0].description == "God object in service layer"


class TestQuerySearch:
    def test_query_search(self, store: GraphStore) -> None:
        """Add entries and search by term in description."""
        add_entry(store, "treat", "best-practice", "Use dependency injection for testability")
        add_entry(store, "treat", "convention", "All API endpoints return JSON")
        add_entry(store, "treat", "optimization", "Cache database queries with TTL")

        results = query_entries(store, "treat", search="database")
        assert len(results) == 1
        assert "database" in results[0].description.lower()

        results = query_entries(store, "treat", search="API")
        assert len(results) == 1
        assert "API" in results[0].description


class TestExportMarkdown:
    def test_export_markdown(self, store: GraphStore, tmp_path: Path) -> None:
        """Add entries, export to markdown, and verify content."""
        add_entry(store, "litter", "failure", "Flaky test due to race condition")
        add_entry(store, "litter", "anti-pattern", "Circular imports between modules")
        add_entry(store, "litter", "failure", "OOM on large file upload", source_agent="tester")

        output_path = tmp_path / "export" / "litter-box.md"
        count = export_markdown(store, "litter", output_path)

        assert count == 3
        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "# Litter Box" in content
        assert "## anti-pattern" in content
        assert "## failure" in content
        assert "Flaky test due to race condition" in content
        assert "Circular imports between modules" in content
        assert "_(agent: tester)_" in content


class TestEmptyQuery:
    def test_empty_query(self, store: GraphStore) -> None:
        """Query empty table returns empty list."""
        entries = query_entries(store, "litter")
        assert entries == []

        entries = query_entries(store, "treat")
        assert entries == []


class TestInvalidBox:
    def test_invalid_box_add(self, store: GraphStore) -> None:
        """add_entry with an invalid box raises ValueError."""
        with pytest.raises(ValueError, match="Invalid box"):
            add_entry(store, "invalid", "failure", "should not work")

    def test_invalid_box_query(self, store: GraphStore) -> None:
        """query_entries with an invalid box raises ValueError."""
        with pytest.raises(ValueError, match="Invalid box"):
            query_entries(store, "invalid")

    def test_invalid_box_export(self, store: GraphStore, tmp_path: Path) -> None:
        """export_markdown with an invalid box raises ValueError."""
        with pytest.raises(ValueError, match="Invalid box"):
            export_markdown(store, "invalid", tmp_path / "nope.md")

    def test_invalid_category(self, store: GraphStore) -> None:
        """add_entry with an invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Invalid category"):
            add_entry(store, "litter", "bogus-category", "should not work")
