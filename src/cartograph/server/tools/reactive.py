"""Graph-reactive loop tools."""

from __future__ import annotations

import re
from typing import Any, cast

from cartograph.server.main import get_last_diff, get_store, mcp

_FILE_PATH_RE = re.compile(r"/|\.(?:py|ts|js)$")


def _entries(result: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """Return a typed diff entry list from a graph diff result."""
    value = result.get(key, [])
    return cast(list[dict[str, Any]], value) if isinstance(value, list) else []


@mcp.tool()
def graph_diff(
    file_paths: list[str] | None = None,
    include_edges: bool = True,
) -> dict[str, Any]:
    """Return what structurally changed in the last indexing run.

    Args:
        file_paths: If provided, filter diff to only these files.
        include_edges: If True (default), include edge-level diff.

    Returns a dict with nodes_added, nodes_removed, nodes_modified,
    edges_added, edges_removed, and a summary.
    """
    last_diff = get_last_diff()
    if last_diff is None:
        return {"error": "No diff available. Run index_codebase first."}

    result = dict(last_diff)

    # Filter by file_paths if provided.
    if file_paths is not None:
        file_set = set(file_paths)
        result["nodes_added"] = [
            n for n in _entries(result, "nodes_added") if n.get("file_path") in file_set
        ]
        result["nodes_removed"] = [
            n for n in _entries(result, "nodes_removed") if n.get("file_path") in file_set
        ]
        result["nodes_modified"] = [
            n for n in _entries(result, "nodes_modified") if n.get("file_path") in file_set
        ]
        if include_edges:
            # Keep edges where source or target qualified_name belongs to a
            # node in the filtered files.  We use the qualified_name sets from
            # the filtered node lists to decide.
            kept_qnames = {
                n["qualified_name"]
                for lst in ("nodes_added", "nodes_removed", "nodes_modified")
                for n in _entries(result, lst)
            }
            result["edges_added"] = [
                e
                for e in _entries(result, "edges_added")
                if e.get("source") in kept_qnames or e.get("target") in kept_qnames
            ]
            result["edges_removed"] = [
                e
                for e in _entries(result, "edges_removed")
                if e.get("source") in kept_qnames or e.get("target") in kept_qnames
            ]

    if not include_edges:
        result.pop("edges_added", None)
        result.pop("edges_removed", None)

    # Recompute summary based on (possibly filtered) result.
    files_affected: set[str] = set()
    for lst_key in ("nodes_added", "nodes_removed", "nodes_modified"):
        for n in _entries(result, lst_key):
            file_path = n.get("file_path")
            if isinstance(file_path, str):
                files_affected.add(file_path)

    summary: dict[str, Any] = {
        "files_affected": len(files_affected),
        "nodes_added": len(_entries(result, "nodes_added")),
        "nodes_removed": len(_entries(result, "nodes_removed")),
        "nodes_modified": len(_entries(result, "nodes_modified")),
    }
    if include_edges:
        summary["edges_added"] = len(_entries(result, "edges_added"))
        summary["edges_removed"] = len(_entries(result, "edges_removed"))

    result["summary"] = summary
    return result


@mcp.tool()
def validate_graph(
    scope: list[str] | None = None,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """Validate graph integrity and detect stale data.

    Args:
        scope: Qualified names or file paths to check. None = all
               (or last diff's changed nodes if available).
        checks: Subset of "dangling_edges", "orphan_nodes",
                "stale_annotations". None = all three.

    Returns a dict with ``passed``, ``issues``, and ``summary``.
    """
    store = get_store()
    if store is None:
        return {"error": "No graph loaded. Run index_codebase first."}

    # Resolve scope into file_paths / qualified_names.
    file_paths: list[str] | None = None
    qualified_names: list[str] | None = None

    if scope is not None:
        fp_list: list[str] = []
        qn_list: list[str] = []
        for entry in scope:
            if _FILE_PATH_RE.search(entry):
                fp_list.append(entry)
            else:
                qn_list.append(entry)
        file_paths = fp_list or None
        qualified_names = qn_list or None
    elif (last_diff := get_last_diff()) is not None:
        # Default to files affected by the last diff.
        diff_files: set[str] = set()
        for lst_key in ("nodes_added", "nodes_removed", "nodes_modified"):
            for n in _entries(last_diff, lst_key):
                file_path = n.get("file_path")
                if isinstance(file_path, str):
                    diff_files.add(file_path)
        if diff_files:
            file_paths = sorted(diff_files)

    issues = store.validate_nodes(
        file_paths=file_paths,
        qualified_names=qualified_names,
        checks=checks,
    )

    # Build summary.
    all_checks = {"dangling_edges", "orphan_nodes", "stale_annotations"}
    active_checks = set(checks) & all_checks if checks else all_checks
    checks_run = len(active_checks)
    errors = sum(1 for i in issues if i["severity"] == "error")
    warnings = sum(1 for i in issues if i["severity"] == "warning")

    passed = len(issues) == 0
    result = {
        "passed": passed,
        "issues": issues,
        "summary": {
            "checks_run": checks_run,
            "errors": errors,
            "warnings": warnings,
            "passed": checks_run - (1 if errors > 0 else 0) - (1 if warnings > 0 else 0),
        },
    }
    if passed:
        result["cleanable"] = True
    return result
