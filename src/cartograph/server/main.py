"""Cartographing Kittens MCP server entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from cartograph.compat import resolve_db_dir, resolve_project_root
from cartograph.storage import GraphStore, create_connection

# Module-level state shared with tool modules.
_store: GraphStore | None = None
_root: Path | None = None
_last_diff: dict | None = None
_last_index_version: int | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Open GraphStore on startup, close on shutdown."""
    global _store, _root

    project_root = resolve_project_root()
    db_dir = resolve_db_dir(project_root)
    db_path = db_dir / "graph.db"

    conn = create_connection(db_path)
    store = GraphStore(conn)

    _store = store
    _root = project_root

    try:
        yield
    finally:
        store.close()
        _store = None
        _root = None


mcp = FastMCP("kitty", lifespan=lifespan)

# When run via `python -m cartograph.server.main`, Python creates separate
# `__main__` and `cartograph.server.main` module objects. Tool modules import
# `from cartograph.server.main import mcp`, which would resolve to a different
# (empty) instance. Alias `__main__` into the canonical module path so both
# refer to the same object.
import sys

if "cartograph.server.main" not in sys.modules:
    sys.modules["cartograph.server.main"] = sys.modules["__main__"]

# Import tool modules so they register with the mcp instance.
import cartograph.server.prompts.annotate  # noqa: E402, F401

# Import prompt modules so they register with the mcp instance.
import cartograph.server.prompts.explore  # noqa: E402, F401
import cartograph.server.prompts.refactor  # noqa: E402, F401
import cartograph.server.tools.analysis  # noqa: E402, F401
import cartograph.server.tools.annotate  # noqa: E402, F401
import cartograph.server.tools.index  # noqa: E402, F401
import cartograph.server.tools.memory  # noqa: E402, F401
import cartograph.server.tools.query  # noqa: E402, F401
import cartograph.server.tools.reactive  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run(transport="stdio")
