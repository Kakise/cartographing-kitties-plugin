"""Cartograph MCP server entry point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from cartograph.storage import GraphStore, create_connection

# Module-level state shared with tool modules.
_store: GraphStore | None = None
_root: Path | None = None


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Open GraphStore on startup, close on shutdown."""
    global _store, _root

    db_dir = Path(os.environ.get("CARTOGRAPH_PROJECT_ROOT", ".")) / ".cartograph"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "graph.db"

    conn = create_connection(db_path)
    store = GraphStore(conn)

    _store = store
    _root = Path(os.environ.get("CARTOGRAPH_PROJECT_ROOT", ".")).resolve()

    try:
        yield
    finally:
        store.close()
        _store = None
        _root = None


mcp = FastMCP("cartograph", lifespan=lifespan)

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
import cartograph.server.tools.query  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run(transport="stdio")
