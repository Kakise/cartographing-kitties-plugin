"""End-to-end tests that run the MCP server over stdio and call tools via JSON-RPC."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from cartograph.compat import resolve_storage_paths

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sample_python_project"
BENCHMARK_DIR = Path(__file__).parent / "fixtures" / "benchmark_project"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_initialize() -> str:
    return json.dumps(
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
    )


def _build_initialized_notification() -> str:
    return json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})


def _build_tool_call(request_id: int, tool_name: str, arguments: dict) -> str:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
    )


def _run_server(
    messages: list[str],
    project_root: str,
    timeout: int = 30,
    *,
    storage_root: str | None = None,
) -> list[dict]:
    """Start the MCP server, send messages, and return parsed JSON-RPC responses."""
    input_data = "\n".join(messages)
    env = {**os.environ, "KITTY_PROJECT_ROOT": project_root}
    if storage_root is not None:
        env["KITTY_STORAGE_ROOT"] = storage_root

    result = subprocess.run(
        [sys.executable, "-m", "cartograph.server.main"],
        input=input_data,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )

    responses = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line:
            responses.append(json.loads(line))
    return responses


def _get_response(responses: list[dict], request_id: int) -> dict:
    """Find a response by its JSON-RPC id."""
    for r in responses:
        if r.get("id") == request_id:
            return r
    raise ValueError(f"No response with id={request_id} in {responses}")


def _parse_tool_result(response: dict) -> dict:
    """Extract the parsed JSON content from a tools/call response."""
    content = response["result"]["content"]
    assert len(content) > 0
    text = content[0]["text"]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    """Copy sample project to tmp so the server can write .pawprints/ in it."""
    dest = tmp_path / "sample_project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


@pytest.fixture()
def benchmark_project(tmp_path: Path) -> Path:
    """Copy benchmark project to tmp."""
    dest = tmp_path / "benchmark_project"
    shutil.copytree(BENCHMARK_DIR, dest)
    return dest


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIndexCodebaseOverStdio:
    """Call index_codebase via stdio and verify results."""

    def test_full_index(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 2))

        assert "error" not in result
        assert result["files_parsed"] > 0
        assert result["nodes_created"] > 0
        assert result["edges_created"] >= 0

    def test_incremental_index_after_full(self, sample_project: Path):
        """Full index then incremental — incremental should parse 0 new files."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "index_codebase", {"full": False}),
        ]
        responses = _run_server(messages, str(sample_project))

        full_result = _parse_tool_result(_get_response(responses, 2))
        assert full_result["files_parsed"] > 0

        incr_result = _parse_tool_result(_get_response(responses, 3))
        assert incr_result["files_parsed"] == 0

    def test_full_index_with_centralized_storage_creates_db(self, sample_project: Path, tmp_path: Path):
        storage_root = tmp_path / "storage"
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
        ]
        responses = _run_server(
            messages,
            str(sample_project),
            storage_root=str(storage_root),
        )
        result = _parse_tool_result(_get_response(responses, 2))

        assert "error" not in result
        paths = resolve_storage_paths(sample_project, storage_root=storage_root)
        assert paths.db_path.exists()

    def test_same_storage_root_keeps_projects_isolated(self, tmp_path: Path):
        storage_root = tmp_path / "storage"
        project_one = tmp_path / "one" / "sample_project"
        project_two = tmp_path / "two" / "sample_project"
        shutil.copytree(FIXTURE_DIR, project_one)
        shutil.copytree(FIXTURE_DIR, project_two)

        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
        ]

        responses_one = _run_server(messages, str(project_one), storage_root=str(storage_root))
        responses_two = _run_server(messages, str(project_two), storage_root=str(storage_root))

        result_one = _parse_tool_result(_get_response(responses_one, 2))
        result_two = _parse_tool_result(_get_response(responses_two, 2))
        assert "error" not in result_one
        assert "error" not in result_two

        first_paths = resolve_storage_paths(project_one, storage_root=storage_root)
        second_paths = resolve_storage_paths(project_two, storage_root=storage_root)
        assert first_paths.db_path.exists()
        assert second_paths.db_path.exists()
        assert first_paths.db_path != second_paths.db_path


class TestQueryNodeOverStdio:
    """Call query_node via stdio after indexing."""

    def test_query_known_class(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "query_node", {"name": "User"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is True
        assert result["node"]["name"] == "User"
        assert result["node"]["kind"] == "class"
        assert isinstance(result["neighbors"], list)

    def test_query_by_qualified_name(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "query_node", {"name": "models.user::User"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is True
        assert result["node"]["qualified_name"] == "models.user::User"

    def test_query_nonexistent(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "query_node", {"name": "DoesNotExist"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is False


class TestSearchOverStdio:
    """Call search via stdio after indexing."""

    def test_search_returns_results(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "search", {"query": "User"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["count"] > 0
        names = {r["name"] for r in result["results"]}
        assert any("User" in n or "user" in n for n in names)

    def test_search_with_kind_filter(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "search", {"query": "User", "kind": "class"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        for r in result["results"]:
            assert r["kind"] == "class"

    def test_search_no_results(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "search", {"query": "xyznonexistent"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["count"] == 0


class TestGetFileStructureOverStdio:
    """Call get_file_structure via stdio after indexing."""

    def test_known_file(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "get_file_structure", {"file_path": "src/models/user.py"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is True
        kinds = {n["kind"] for n in result["nodes"]}
        assert "file" in kinds

    def test_nonexistent_file(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "get_file_structure", {"file_path": "nonexistent.py"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is False


class TestDependencyAnalysisOverStdio:
    """Call find_dependencies and find_dependents via stdio."""

    def test_find_dependencies(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "find_dependencies", {"name": "file::src/main.py"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is True
        assert isinstance(result["dependencies"], list)

    def test_find_dependents(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "find_dependents", {"name": "file::src/models/user.py"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is True
        assert isinstance(result["dependents"], list)

    def test_find_dependencies_nonexistent(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "find_dependencies", {"name": "NonExistent"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["found"] is False


class TestAnnotationOverStdio:
    """Call annotation tools via stdio after indexing."""

    def test_annotation_status_after_index(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "annotation_status", {}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert "error" not in result
        assert result["pending"] > 0
        assert result["annotated"] == 0

    def test_get_pending_annotations(self, sample_project: Path):
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "get_pending_annotations", {"batch_size": 5}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert "error" not in result
        assert result["count"] > 0
        assert len(result["batch"]) > 0
        assert "taxonomy" in result

        first = result["batch"][0]
        assert "qualified_name" in first
        assert "kind" in first

    def test_submit_annotations_roundtrip(self, sample_project: Path):
        """Index → get pending → submit annotations → verify status changed."""
        # Step 1+2: index and get pending nodes
        messages_phase1 = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "get_pending_annotations", {"batch_size": 3}),
        ]
        responses1 = _run_server(messages_phase1, str(sample_project))
        pending_result = _parse_tool_result(_get_response(responses1, 3))
        assert pending_result["count"] > 0

        # Build annotations for the pending nodes
        annotations = [
            {
                "qualified_name": node["qualified_name"],
                "summary": f"Test summary for {node['qualified_name']}",
                "tags": ["test", "e2e"],
                "role": "test component",
            }
            for node in pending_result["batch"]
        ]

        # Step 3+4: in a new server session, index again, submit, check status
        messages_phase2 = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "submit_annotations", {"annotations": annotations}),
            _build_tool_call(4, "annotation_status", {}),
        ]
        responses2 = _run_server(messages_phase2, str(sample_project))

        submit_result = _parse_tool_result(_get_response(responses2, 3))
        assert "error" not in submit_result
        assert submit_result["written"] > 0
        assert submit_result["failed"] == 0

        status_result = _parse_tool_result(_get_response(responses2, 4))
        assert status_result["annotated"] > 0


class TestFullWorkflowOverStdio:
    """Test a complete workflow: index → query → search → analyze → annotate."""

    def test_full_workflow_on_benchmark_project(self, benchmark_project: Path):
        """Run all 9 tools in sequence on the benchmark project."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            # 1. Full index
            _build_tool_call(2, "index_codebase", {"full": True}),
            # 2. Query a known class
            _build_tool_call(3, "query_node", {"name": "User"}),
            # 3. Search for a domain term
            _build_tool_call(4, "search", {"query": "order"}),
            # 4. Get file structure
            _build_tool_call(5, "get_file_structure", {"file_path": "src/models/user.py"}),
            # 5. Find dependencies
            _build_tool_call(6, "find_dependencies", {"name": "file::src/main.py"}),
            # 6. Find dependents
            _build_tool_call(7, "find_dependents", {"name": "file::src/models/user.py"}),
            # 7. Annotation status
            _build_tool_call(8, "annotation_status", {}),
            # 8. Get pending annotations
            _build_tool_call(9, "get_pending_annotations", {"batch_size": 3}),
        ]
        responses = _run_server(messages, str(benchmark_project))

        # Verify index
        index_result = _parse_tool_result(_get_response(responses, 2))
        assert index_result["files_parsed"] >= 25
        assert index_result["nodes_created"] > 50

        # Verify query
        query_result = _parse_tool_result(_get_response(responses, 3))
        assert query_result["found"] is True
        assert query_result["node"]["name"] == "User"

        # Verify search
        search_result = _parse_tool_result(_get_response(responses, 4))
        assert search_result["count"] > 0

        # Verify file structure
        file_result = _parse_tool_result(_get_response(responses, 5))
        assert file_result["found"] is True

        # Verify dependencies
        deps_result = _parse_tool_result(_get_response(responses, 6))
        assert deps_result["found"] is True

        # Verify dependents
        dependents_result = _parse_tool_result(_get_response(responses, 7))
        assert dependents_result["found"] is True

        # Verify annotation status
        status_result = _parse_tool_result(_get_response(responses, 8))
        assert status_result["pending"] > 0

        # Verify pending annotations
        pending_result = _parse_tool_result(_get_response(responses, 9))
        assert pending_result["count"] > 0

        # 9. Submit annotations for the pending nodes
        annotations = [
            {
                "qualified_name": node["qualified_name"],
                "summary": f"E2E test annotation for {node['qualified_name']}",
                "tags": ["e2e-test"],
                "role": "tested component",
            }
            for node in pending_result["batch"]
        ]

        messages2 = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(3, "submit_annotations", {"annotations": annotations}),
            _build_tool_call(4, "annotation_status", {}),
        ]
        responses2 = _run_server(messages2, str(benchmark_project))

        submit_result = _parse_tool_result(_get_response(responses2, 3))
        assert submit_result["written"] > 0

        final_status = _parse_tool_result(_get_response(responses2, 4))
        assert final_status["annotated"] > 0


class TestErrorHandlingOverStdio:
    """Verify graceful error handling over stdio."""

    def test_query_before_index(self, sample_project: Path):
        """Querying before indexing should return found=False, not crash."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "query_node", {"name": "User"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 2))

        assert result["found"] is False

    def test_search_before_index(self, sample_project: Path):
        """Searching before indexing should return 0 results."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "search", {"query": "User"}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 2))

        assert result["count"] == 0

    def test_annotation_status_before_index(self, sample_project: Path):
        """Annotation status before indexing should return all zeros."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "annotation_status", {}),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 2))

        assert result["pending"] == 0
        assert result["annotated"] == 0

    def test_submit_invalid_annotations(self, sample_project: Path):
        """Submitting annotations for nonexistent nodes should skip them gracefully."""
        messages = [
            _build_initialize(),
            _build_initialized_notification(),
            _build_tool_call(2, "index_codebase", {"full": True}),
            _build_tool_call(
                3,
                "submit_annotations",
                {
                    "annotations": [
                        {
                            "qualified_name": "nonexistent::Ghost",
                            "summary": "Ghost node",
                            "tags": [],
                            "role": "",
                        }
                    ]
                },
            ),
        ]
        responses = _run_server(messages, str(sample_project))
        result = _parse_tool_result(_get_response(responses, 3))

        assert result["written"] == 0
        assert result["skipped"] == 1
