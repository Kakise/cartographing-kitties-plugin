"""Cartograph: AST-powered codebase intelligence framework for AI coding agents."""

__version__ = "0.1.0"


def main() -> None:
    """CLI entry point — starts the Cartograph MCP server over stdio."""
    from cartograph.server.main import mcp

    mcp.run(transport="stdio")
