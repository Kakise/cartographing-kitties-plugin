"""SQLite connection factory for the Cartograph graph store."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from cartograph.storage.migrations import run_migrations

logger = logging.getLogger(__name__)

# Migrations whose SQL depends on the sqlite_vec extension being loaded on the
# connection.  When the extension is unavailable we skip these and keep the
# database usable in degraded mode (lexical + centrality search continue to
# work; only the dense leg of hybrid search is disabled).
_VEC_DEPENDENT_MIGRATIONS: set[int] = {6}

_VEC_FLAG_ATTR = "_kitty_vec_available"


class _CartographConnection(sqlite3.Connection):
    """sqlite3.Connection subclass that supports a ``__dict__``.

    The base ``sqlite3.Connection`` has no ``__dict__`` and rejects ad-hoc
    attribute writes, so we use a thin subclass to stamp the
    ``_kitty_vec_available`` flag without standing up a separate id-keyed
    registry that would need lifecycle bookkeeping.
    """


def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    """Best-effort load of the sqlite_vec extension.

    Returns True when the extension is loaded and ``vec0`` virtual tables can
    be created on this connection.  Any failure path returns False and logs a
    warning so the caller can keep the connection in degraded mode.
    """
    try:
        import sqlite_vec
    except ImportError:
        logger.warning(
            "Hybrid search in degraded mode: dense channel disabled "
            "(sqlite_vec not installed; install with `uv sync --all-extras`)."
        )
        return False

    try:
        conn.enable_load_extension(True)
    except (sqlite3.NotSupportedError, AttributeError) as exc:
        logger.warning(
            "Hybrid search in degraded mode: dense channel disabled "
            "(enable_load_extension unavailable on this Python build: %s).",
            exc,
        )
        return False

    try:
        sqlite_vec.load(conn)
    except Exception as exc:  # noqa: BLE001 — sqlite-vec surfaces several error types.
        logger.warning(
            "Hybrid search in degraded mode: dense channel disabled (sqlite_vec.load failed: %s).",
            exc,
        )
        return False
    finally:
        try:
            conn.enable_load_extension(False)
        except (sqlite3.NotSupportedError, AttributeError):
            pass

    return True


def is_vec_available(conn: sqlite3.Connection) -> bool:
    """Return whether sqlite_vec is loaded on *conn*.

    Reads the flag stamped on the connection by :func:`create_connection`.
    Returns False when the flag is missing (foreign connection, raw factory)
    so callers can default-deny the dense channel in unfamiliar environments.
    """
    return bool(getattr(conn, _VEC_FLAG_ATTR, False))


def create_connection(db_path: str | Path, *, check_same_thread: bool = True) -> sqlite3.Connection:
    """Create and configure a SQLite connection with optimised settings.

    Opens the database at *db_path* (created if it does not exist), applies
    performance pragmas, enables foreign keys, attempts to load the
    ``sqlite_vec`` extension for the hybrid-search dense channel, and runs
    schema migrations.  When the extension fails to load the connection stays
    fully functional — only the dense leg of :meth:`GraphStore.search` is
    disabled, and migrations that require ``vec0`` are skipped.
    """
    db_path = str(db_path)
    conn = sqlite3.connect(
        db_path,
        check_same_thread=check_same_thread,
        factory=_CartographConnection,
    )
    conn.row_factory = sqlite3.Row

    # Performance and reliability pragmas
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -65536")  # 64 MB
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")

    vec_available = _try_load_sqlite_vec(conn)
    setattr(conn, _VEC_FLAG_ATTR, vec_available)

    skip = None if vec_available else _VEC_DEPENDENT_MIGRATIONS
    run_migrations(conn, skip_versions=skip)

    return conn
