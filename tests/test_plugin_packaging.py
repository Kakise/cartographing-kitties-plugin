from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_root_codex_plugin_manifest_paths_exist() -> None:
    manifest_path = REPO_ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())

    skills_path = REPO_ROOT / manifest["skills"]
    mcp_path = REPO_ROOT / manifest["mcpServers"]

    assert skills_path.exists()
    assert mcp_path.exists()


def test_agent_manifest_declares_all_framework_agents() -> None:
    agents_dir = REPO_ROOT / "plugins" / "kitty" / "agents"
    manifest_path = agents_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    declared_paths = {entry["path"] for entry in manifest["agents"]}
    declared_names = {entry["name"] for entry in manifest["agents"]}
    actual_agent_files = {
        f"./{path.name}" for path in agents_dir.glob("*.md") if path.name != "README.md"
    }
    actual_agent_names = {path.stem for path in agents_dir.glob("*.md") if path.name != "README.md"}

    assert declared_paths == actual_agent_files
    assert declared_names == actual_agent_names


def test_agent_manifest_marks_dual_runtime_intent() -> None:
    manifest_path = REPO_ROOT / "plugins" / "kitty" / "agents" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    for entry in manifest["agents"]:
        runtimes = entry["runtimes"]
        assert runtimes["claude_code"] == "directory-discovered"
        assert runtimes["codex"] == "framework-declared"


def test_workflow_contract_docs_exist() -> None:
    assert (REPO_ROOT / "docs" / "architecture" / "codex-workflow-contract.md").exists()
    assert (REPO_ROOT / "docs" / "architecture" / "repo-boundaries.md").exists()
