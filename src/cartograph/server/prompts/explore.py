"""Guided codebase exploration prompt."""

from __future__ import annotations

from cartograph.server.main import mcp


@mcp.prompt()
def explore_codebase(focus: str = "") -> str:
    """Guide an agent through exploring and understanding a codebase."""
    focus_instruction = ""
    if focus:
        focus_instruction = (
            f"\n2. Since the focus is '{focus}', start by calling "
            f"query_node with that name to understand it directly. "
            f"If it is a file path, use get_file_structure instead."
        )
    else:
        focus_instruction = (
            "\n2. Call get_file_structure to see the top-level layout "
            "of the project and identify key modules."
        )

    return (
        "You are exploring a codebase using Cartographing Kittens' structural tools.\n"
        "\n"
        "Follow these steps:\n"
        "\n"
        "1. Call index_codebase if the project has not been indexed yet. "
        "This parses the source files and builds the dependency graph."
        f"{focus_instruction}\n"
        "3. Use query_node on interesting names from the results to see "
        "their neighbors — imports, calls, and inheritance relationships.\n"
        "4. Build a mental map of the architecture by tracing how key "
        "modules connect to each other.\n"
        "5. Summarize your findings: main entry points, core abstractions, "
        "and the overall dependency flow."
    )
