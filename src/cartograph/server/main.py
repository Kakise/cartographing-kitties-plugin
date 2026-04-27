"""Cartographing Kittens MCP server entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from cartograph.compat import StoragePaths, resolve_storage_paths
from cartograph.storage import GraphStore, create_connection


@dataclass(slots=True)
class ServerContext:
    """Runtime resources owned by one MCP server lifespan."""

    store: GraphStore
    root: Path
    storage_paths: StoragePaths


# Runtime state shared with tool modules. The legacy module-level attributes are
# kept for tests and older integrations that wire state directly.
_context: ServerContext | None = None
_store: GraphStore | None = None
_root: Path | None = None
_storage_paths: StoragePaths | None = None
_last_diff: dict[str, Any] | None = None
_last_index_version: int | None = None


def set_context(context: ServerContext) -> None:
    """Install runtime context and mirror it to legacy module attributes."""
    global _context, _store, _root, _storage_paths

    _context = context
    _store = context.store
    _root = context.root
    _storage_paths = context.storage_paths


def clear_context() -> None:
    """Clear runtime context and per-session state."""
    global _context, _store, _root, _storage_paths, _last_diff, _last_index_version

    _context = None
    _store = None
    _root = None
    _storage_paths = None
    _last_diff = None
    _last_index_version = None


def get_context() -> ServerContext | None:
    """Return the active runtime context, including legacy test wiring."""
    if _context is not None:
        return _context
    if _store is not None and _root is not None and _storage_paths is not None:
        return ServerContext(store=_store, root=_root, storage_paths=_storage_paths)
    return None


def get_store() -> GraphStore | None:
    """Return the active graph store, including legacy test wiring."""
    context = get_context()
    if context is not None:
        return context.store
    return _store


def get_last_diff() -> dict[str, Any] | None:
    """Return the structural diff from the last indexing pass."""
    return _last_diff


def set_last_diff(diff: dict[str, Any]) -> None:
    """Store the structural diff from the latest indexing pass."""
    global _last_diff

    _last_diff = diff


@asynccontextmanager
async def lifespan(_server: FastMCP):
    """Open GraphStore on startup, close on shutdown."""
    paths = resolve_storage_paths()

    conn = create_connection(paths.db_path)
    store = GraphStore(conn)
    set_context(ServerContext(store=store, root=paths.project_root, storage_paths=paths))

    try:
        yield
    finally:
        store.close()
        clear_context()


mcp = FastMCP("kitty", lifespan=lifespan)

# When run via `python -m cartograph.server.main`, Python creates separate
# `__main__` and `cartograph.server.main` module objects. Tool modules import
# `from cartograph.server.main import mcp`, which would resolve to a different
# (empty) instance. Alias `__main__` into the canonical module path so both
# refer to the same object.
import sys

if "cartograph.server.main" not in sys.modules:
    sys.modules["cartograph.server.main"] = sys.modules["__main__"]

_REGISTRATION_MODULES = (
    "cartograph.server.prompts.annotate",
    "cartograph.server.prompts.explore",
    "cartograph.server.prompts.refactor",
    "cartograph.server.tools.analysis",
    "cartograph.server.tools.annotate",
    "cartograph.server.tools.index",
    "cartograph.server.tools.memory",
    "cartograph.server.tools.query",
    "cartograph.server.tools.reactive",
)


def register_mcp_modules() -> None:
    """Import prompt and tool modules so decorators register with FastMCP."""
    for module_name in _REGISTRATION_MODULES:
        import_module(module_name)


register_mcp_modules()

if __name__ == "__main__":
    mcp.run(transport="stdio")
