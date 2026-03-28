"""Web graph explorer entry point."""


def serve(port: int = 3333, project_root: str = ".") -> None:
    """CLI entry point — starts the web graph explorer (kitty-graph command)."""
    import sys

    from cartograph.compat import resolve_db_dir

    db_dir = resolve_db_dir(project_root)
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
        run_server(store, port=port)
    finally:
        store.close()
