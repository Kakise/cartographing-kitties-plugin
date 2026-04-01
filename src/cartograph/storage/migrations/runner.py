"""Lightweight schema migration runner for SQLite.

Uses a single-row ``schema_version`` table and ordered ``.sql`` files in the
``migrations/`` directory.  Designed to replace Alembic for this project so we
avoid pulling in SQLAlchemy as a transitive dependency.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent

_SCHEMA_VERSION_DDL = """\
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL DEFAULT 0
);
"""


def _ensure_version_table(conn: sqlite3.Connection) -> int:
    """Create the version table if missing and return the current version."""
    conn.executescript(_SCHEMA_VERSION_DDL)
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (0)")
        conn.commit()
        return 0
    return int(row[0])


def _detect_existing_db(conn: sqlite3.Connection) -> bool:
    """Return True if the database already has the ``nodes`` table.

    This is used to detect databases created before the migration system
    existed so we can stamp them at the baseline version.
    """
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nodes'").fetchone()
    return row is not None


def _discover_migrations(directory: Path) -> list[tuple[int, Path]]:
    """Return ``(version, path)`` pairs sorted by version number.

    Migration files are named ``NNNN_<description>.sql`` where *NNNN* is a
    zero-padded version number.
    """
    migrations: list[tuple[int, Path]] = []
    for sql_file in sorted(directory.glob("*.sql")):
        prefix = sql_file.stem.split("_", 1)[0]
        try:
            version = int(prefix)
        except ValueError:
            continue
        migrations.append((version, sql_file))
    return migrations


def run_migrations(conn: sqlite3.Connection) -> int:
    """Apply pending migrations and return the new schema version.

    For a **fresh database** (no tables at all) all migrations run from
    scratch.  For an **existing database** that predates the migration system
    (has ``nodes`` but no ``schema_version``), the baseline migration (0001)
    is skipped and the version is stamped to 1.
    """
    has_existing_tables = _detect_existing_db(conn)
    current_version = _ensure_version_table(conn)

    # Existing DB with no migration history → stamp as baseline.
    if has_existing_tables and current_version == 0:
        logger.info("Existing database detected — stamping as baseline (v1)")
        conn.execute("UPDATE schema_version SET version = 1")
        conn.commit()
        current_version = 1

    migrations = _discover_migrations(MIGRATIONS_DIR)

    applied = 0
    for version, sql_path in migrations:
        if version <= current_version:
            continue
        sql = sql_path.read_text(encoding="utf-8")
        logger.info("Applying migration %04d: %s", version, sql_path.name)
        try:
            conn.executescript(sql)
            conn.execute("UPDATE schema_version SET version = ?", (version,))
            conn.commit()
            applied += 1
        except Exception:
            logger.exception("Migration %04d failed — rolling back", version)
            conn.rollback()
            raise

    if applied:
        logger.info("Applied %d migration(s), now at version %d", applied, version)

    return conn.execute("SELECT version FROM schema_version").fetchone()[0]
