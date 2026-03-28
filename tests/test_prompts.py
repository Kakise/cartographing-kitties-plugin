"""Tests for the Cartograph MCP server prompts."""

from __future__ import annotations

import json
import subprocess
import sys

from cartograph.server.main import mcp
from cartograph.server.prompts.annotate import annotate_batch
from cartograph.server.prompts.explore import explore_codebase
from cartograph.server.prompts.refactor import plan_refactor


class TestPromptRegistration:
    """Verify prompts are registered on the mcp instance."""

    def test_prompts_are_registered(self):
        # Access the prompt manager to check registration.
        prompt_manager = mcp._prompt_manager
        prompts = prompt_manager._prompts
        prompt_names = set(prompts.keys())
        expected = {"explore_codebase", "plan_refactor", "annotate_batch"}
        assert expected.issubset(prompt_names), f"Missing prompts: {expected - prompt_names}"

    def test_prompt_count(self):
        prompt_manager = mcp._prompt_manager
        prompts = prompt_manager._prompts
        assert len(prompts) >= 3


class TestExploreCodebase:
    """Test the explore_codebase prompt."""

    def test_returns_nonempty_string(self):
        result = explore_codebase()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_exploration_guidance(self):
        result = explore_codebase()
        assert "index_codebase" in result
        assert "get_file_structure" in result

    def test_with_focus_parameter(self):
        result = explore_codebase(focus="UserService")
        assert "UserService" in result
        assert "query_node" in result

    def test_without_focus_parameter(self):
        result = explore_codebase(focus="")
        assert "get_file_structure" in result


class TestPlanRefactor:
    """Test the plan_refactor prompt."""

    def test_returns_nonempty_string(self):
        result = plan_refactor(target="MyClass")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_target_name(self):
        result = plan_refactor(target="UserService")
        assert "UserService" in result

    def test_contains_refactoring_guidance(self):
        result = plan_refactor(target="SomeFunction")
        assert "find_dependents" in result
        assert "find_dependencies" in result
        assert "query_node" in result
        assert "test" in result.lower()


class TestAnnotateBatch:
    """Test the annotate_batch prompt."""

    def test_returns_nonempty_string(self):
        result = annotate_batch()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_annotation_guidance(self):
        result = annotate_batch()
        assert "annotation_status" in result
        assert "get_pending_annotations" in result
        assert "submit_annotations" in result

    def test_custom_batch_size(self):
        result = annotate_batch(batch_size=5)
        assert "5" in result

    def test_default_batch_size(self):
        result = annotate_batch()
        assert "10" in result

    def test_batch_size_zero(self):
        result = annotate_batch(batch_size=0)
        assert isinstance(result, str)
        assert len(result) > 0


class TestPromptsCoexistWithTools:
    """Verify prompts and tools coexist on the same mcp instance."""

    def test_tools_still_registered(self):
        tool_manager = mcp._tool_manager
        tools = tool_manager._tools
        expected_tools = {
            "index_codebase",
            "annotation_status",
            "query_node",
            "search",
            "get_file_structure",
            "find_dependencies",
            "find_dependents",
            "get_pending_annotations",
            "submit_annotations",
        }
        tool_names = set(tools.keys())
        assert expected_tools.issubset(tool_names)

    def test_both_tools_and_prompts_present(self):
        tool_manager = mcp._tool_manager
        prompt_manager = mcp._prompt_manager
        assert len(tool_manager._tools) >= 9
        assert len(prompt_manager._prompts) >= 3


class TestStdioPromptDiscovery:
    """Verify prompts are discoverable over stdio transport."""

    def test_prompts_list_returns_prompts_over_stdio(self):
        """Start the server as a subprocess and verify prompts/list returns all 3 prompts."""
        handshake = "\n".join(
            [
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0"},
                        },
                    }
                ),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}}),
            ]
        )

        result = subprocess.run(
            [sys.executable, "-m", "cartograph.server.main"],
            input=handshake,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse each JSON response line.
        responses = [json.loads(line) for line in result.stdout.strip().splitlines()]

        # Find the prompts/list response.
        prompts_response = next(r for r in responses if r.get("id") == 2)
        prompt_names = {p["name"] for p in prompts_response["result"]["prompts"]}

        expected_prompts = {"explore_codebase", "plan_refactor", "annotate_batch"}
        assert prompt_names == expected_prompts
