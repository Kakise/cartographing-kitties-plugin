"""Cartograph: AST-powered codebase intelligence framework for AI coding agents."""

__version__ = "0.1.0"


def main() -> None:
    """CLI entry point — starts the MCP server (default) or web explorer (--serve)."""
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(
        prog="cartographing-kittens",
        description="AST-powered codebase intelligence for AI coding agents",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start the web graph explorer instead of the MCP server",
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

    if args.serve:
        db_path = Path(args.project_root) / ".cartograph" / "graph.db"
        if not db_path.exists():
            print(
                f"No graph database found at {db_path}\n"
                "Run 'uvx cartographing-kittens' as an MCP server first to index your codebase.",
                file=sys.stderr,
            )
            sys.exit(1)

        import sqlite3

        from cartograph.storage import GraphStore
        from cartograph.storage.schema import SCHEMA_SQL
        from cartograph.web.server import run_server

        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA_SQL)
        store = GraphStore(conn)
        try:
            run_server(store, port=args.port)
        finally:
            store.close()
    else:
        from cartograph.server.main import mcp

        mcp.run(transport="stdio")
