"""Tests for the schema migration system."""

from __future__ import annotations

import sqlite3
import textwrap
from pathlib import Path

import pytest

from cartograph.storage.migrations.runner import (
    _detect_existing_db,
    _discover_migrations,
    _ensure_version_table,
    run_migrations,
)


@pytest.fixture()
def db_conn(tmp_path: Path):
    """Fresh in-memory-like SQLite connection (actually on disk for WAL)."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    yield conn
    conn.close()


class TestEnsureVersionTable:
    def test_creates_table_on_fresh_db(self, db_conn: sqlite3.Connection):
        version = _ensure_version_table(db_conn)
        assert version == 0

    def test_returns_existing_version(self, db_conn: sqlite3.Connection):
        _ensure_version_table(db_conn)
        db_conn.execute("UPDATE schema_version SET version = 5")
        db_conn.commit()
        assert _ensure_version_table(db_conn) == 5


class TestDetectExistingDb:
    def test_fresh_db_returns_false(self, db_conn: sqlite3.Connection):
        assert _detect_existing_db(db_conn) is False

    def test_db_with_nodes_returns_true(self, db_conn: sqlite3.Connection):
        db_conn.execute("CREATE TABLE nodes (id INTEGER PRIMARY KEY)")
        assert _detect_existing_db(db_conn) is True


class TestDiscoverMigrations:
    def test_discovers_sql_files(self, tmp_path: Path):
        (tmp_path / "0001_baseline.sql").write_text("SELECT 1;")
        (tmp_path / "0002_add_stuff.sql").write_text("SELECT 2;")
        (tmp_path / "not_a_migration.txt").write_text("nope")
        migrations = _discover_migrations(tmp_path)
        assert len(migrations) == 2
        assert migrations[0][0] == 1
        assert migrations[1][0] == 2

    def test_sorted_by_version(self, tmp_path: Path):
        (tmp_path / "0003_c.sql").write_text("")
        (tmp_path / "0001_a.sql").write_text("")
        (tmp_path / "0002_b.sql").write_text("")
        migrations = _discover_migrations(tmp_path)
        assert [v for v, _ in migrations] == [1, 2, 3]


class TestRunMigrations:
    def test_fresh_db_runs_all_migrations(self, db_conn: sqlite3.Connection):
        """Running on a fresh DB should apply the baseline migration."""
        version = run_migrations(db_conn)
        assert version >= 1
        # The nodes table should exist after baseline
        row = db_conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'"
        ).fetchone()
        assert row is not None

    def test_existing_db_stamps_baseline(self, db_conn: sqlite3.Connection):
        """An existing DB with full schema but no schema_version gets stamped at v1."""
        # Simulate a pre-migration database that has the full original schema
        from cartograph.storage.migrations import runner

        baseline = (runner.MIGRATIONS_DIR / "0001_baseline.sql").read_text()
        db_conn.executescript(baseline)
        version = run_migrations(db_conn)
        assert version >= 1

    def test_idempotent_on_current_db(self, db_conn: sqlite3.Connection):
        """Running migrations twice should be a no-op the second time."""
        v1 = run_migrations(db_conn)
        v2 = run_migrations(db_conn)
        assert v1 == v2

    def test_create_connection_uses_migrations(self, tmp_path: Path):
        """The create_connection factory should produce a fully migrated DB."""
        from cartograph.storage.connection import create_connection

        conn = create_connection(tmp_path / "graph.db")
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row[0] >= 1
        # Verify nodes table exists
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'"
        ).fetchone()
        assert row is not None
        conn.close()
