"""Cartograph: AST-powered codebase intelligence framework for AI coding agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cartographing-kittens")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


def main() -> None:
    """CLI entry point — starts the MCP server."""
    from cartograph.server.main import mcp

    mcp.run(transport="stdio")


def serve() -> None:
    """CLI entry point — starts the web graph explorer (kitty-graph command)."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="kitty-graph",
        description="Interactive web explorer for the Cartographing Kittens code graph",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3333,
        help="Port for the web explorer (default: 3333)",
    )
    parser.add_argument(
        "--project-root",
        type=str,
        default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args()

    from cartograph.compat import resolve_db_dir

    db_dir = resolve_db_dir(args.project_root)
    db_path = db_dir / "graph.db"
    if not db_path.exists():
        print(
            f"No graph database found at {db_path}\n"
            "Run 'uvx cartographing-kittens' as an MCP server first to index your codebase.",
            file=sys.stderr,
        )
        sys.exit(1)

    from cartograph.storage import GraphStore
    from cartograph.storage.connection import create_connection
    from cartograph.web.server import run_server

    conn = create_connection(db_path, check_same_thread=False)
    store = GraphStore(conn)
    try:
        run_server(store, port=args.port)
    finally:
        store.close()
