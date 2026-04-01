"""SQLite connection factory for the Cartograph graph store."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from cartograph.storage.migrations import run_migrations


def create_connection(db_path: str | Path, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Create and configure a SQLite connection with optimized settings.

    Opens the database at *db_path* (created if it does not exist), applies
    performance pragmas, enables foreign keys, and runs schema migrations.
    """
    db_path = str(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row

    # Performance and reliability pragmas
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -65536")  # 64 MB
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")

    # Apply schema migrations (creates tables on fresh DBs, upgrades existing ones)
    run_migrations(conn)

    return conn
