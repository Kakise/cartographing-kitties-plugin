"""Guided refactoring planning prompt."""

from __future__ import annotations

from cartograph.server.main import mcp


@mcp.prompt()
def plan_refactor(target: str) -> str:
    """Guide an agent through planning a safe refactor of a symbol or file."""
    return (
        f"You are planning a refactor of '{target}' using Cartographing Kittens' "
        "structural analysis tools.\n"
        "\n"
        "Follow these steps:\n"
        "\n"
        f"1. Call query_node for '{target}' to understand what it is "
        "(function, class, module) and see its metadata.\n"
        f"2. Call find_dependents on '{target}' to assess the blast radius "
        "-- these are all the places that will be affected by your change.\n"
        f"3. Call find_dependencies on '{target}' to understand what it "
        "relies on -- you need to preserve or update these relationships.\n"
        "4. Among the dependents, identify any test files (look for "
        "'test_' prefixes or '/tests/' in paths). These tests must be "
        "updated to match the refactored code.\n"
        "5. Produce a refactoring plan that lists:\n"
        "   - The proposed change\n"
        "   - Every file that needs modification (from dependents)\n"
        "   - Every test that needs updating\n"
        "   - The order of changes to keep the codebase passing at each step"
    )
