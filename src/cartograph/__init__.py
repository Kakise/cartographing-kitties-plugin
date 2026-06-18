"""Cartograph: AST-powered codebase intelligence framework for AI coding agents."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cartographing-kittens")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"


def main() -> None:
    """CLI entry point.

    With no arguments, starts the MCP server over stdio (the default the plugin
    invokes via ``uvx cartographing-kittens``). The ``plan`` subcommand
    (``cartographing-kittens plan <report|audit|set-unit|set-status> ...``)
    delegates to the shipped plan-state CLI so end users get plan tooling
    without a separate script.
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        from cartograph.planning.cli import main as plan_main

        raise SystemExit(plan_main(sys.argv[2:]))

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
    parser.add_argument(
        "--storage-root",
        type=str,
        default=None,
        help="Centralized storage root for per-project graph data (default: disabled)",
    )

    args = parser.parse_args()

    from cartograph.compat import resolve_storage_paths

    paths = resolve_storage_paths(args.project_root, storage_root=args.storage_root)
    if not paths.db_path.exists():
        print(
            f"No graph database found at {paths.db_path}\n"
            "Run 'uvx cartographing-kittens' as an MCP server first to index your codebase.",
            file=sys.stderr,
        )
        sys.exit(1)

    from cartograph.storage import GraphStore
    from cartograph.storage.connection import create_connection
    from cartograph.web.server import run_server

    conn = create_connection(paths.db_path, check_same_thread=False)
    store = GraphStore(conn)
    try:
        run_server(store, port=args.port)
    finally:
        store.close()
