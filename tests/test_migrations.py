"""Tests for the schema migration system."""

from __future__ import annotations

import sqlite3
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
    """Fresh on-disk SQLite connection with sqlite_vec loaded when available.

    We mirror the production loading order in ``create_connection`` so that
    migrations which depend on the ``vec0`` virtual table (e.g.
    ``0006_hybrid_search.sql``) can apply.  When sqlite_vec is unavailable
    the test falls back to skipping just those migrations, exercising the
    degraded-mode path in ``run_migrations``.
    """
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (ImportError, sqlite3.NotSupportedError, sqlite3.OperationalError):
        pass
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

    def test_skip_versions_stamps_without_running_sql(self, tmp_path: Path):
        """When a migration is in skip_versions its SQL is bypassed but the
        schema_version stamp still advances so subsequent migrations apply.
        """
        # A bare connection with no sqlite_vec loaded — migration 0006 would
        # fail with "no such module: vec0" if executed.
        db_path = tmp_path / "skip.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            version = run_migrations(conn, skip_versions={6})
            assert version >= 6
            # nodes_vec must NOT exist when 0006 is skipped.
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes_vec'"
            ).fetchone()
            assert row is None
            # But the regular tables created by earlier migrations should be present.
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


class TestVecExtension:
    """Cover sqlite_vec extension loading and the nodes_vec virtual table."""

    def test_create_connection_creates_nodes_vec_when_vec_loads(self, tmp_path: Path):
        """When sqlite_vec is importable and loadable, the connection factory
        must load it, set ``_kitty_vec_available=True``, and create the
        ``nodes_vec`` virtual table via migration 0006.
        """
        sqlite_vec = pytest.importorskip("sqlite_vec")  # noqa: F841
        from cartograph.storage.connection import create_connection, is_vec_available

        conn = create_connection(tmp_path / "vec.db")
        try:
            assert is_vec_available(conn) is True
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='nodes_vec'"
            ).fetchone()
            assert row is not None, "nodes_vec virtual table should exist"
        finally:
            conn.close()

    def test_create_connection_degraded_mode_when_load_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Simulate sqlite_vec.load failing.  The connection must still be
        usable, ``_kitty_vec_available`` must be False, and ``nodes_vec``
        must not exist (migration 0006 was skipped).
        """
        import sqlite_vec

        from cartograph.storage import connection as connection_module

        def _fail_load(*_args, **_kwargs):
            raise RuntimeError("simulated extension load failure")

        monkeypatch.setattr(sqlite_vec, "load", _fail_load)
        conn = connection_module.create_connection(tmp_path / "degraded.db")
        try:
            assert connection_module.is_vec_available(conn) is False
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='nodes_vec'"
            ).fetchone()
            assert row is None, "nodes_vec must not exist in degraded mode"
            # Other migrations still applied — sanity-check on `nodes`.
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='nodes'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()
