from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "plugins" / "kitty" / "_source" / "agents"
ANNOTATOR_NAMES = {"cartographing-kitten"}
RESEARCH_REVIEW_TOOL_BUDGET = {"Read", "Grep", "Glob"}
ANNOTATOR_TOOL_BUDGET = {"Read", "Grep", "Glob", "Bash"}
EXPECTED_LIBRARIAN_EXPERT_MCP_TOOLS = {
    "query_node",
    "search",
    "get_file_structure",
    "find_dependencies",
    "find_dependents",
    "rank_nodes",
}


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_agent_generator_check_is_clean() -> None:
    result = _run_script("scripts/generate_agents.py", "--check")

    assert result.returncode == 0, result.stderr


def test_manifest_generator_check_is_clean() -> None:
    result = _run_script("scripts/generate_manifests.py", "--check")

    assert result.returncode == 0, result.stderr


def test_agent_sources_drive_manifest_and_codex_outputs() -> None:
    source_dir = REPO_ROOT / "plugins" / "kitty" / "_source" / "agents"
    source_names = {path.stem for path in source_dir.glob("*.yaml")}
    manifest = json.loads(
        (REPO_ROOT / "plugins" / "kitty" / "agents" / "manifest.json").read_text()
    )
    manifest_names = {entry["name"] for entry in manifest["agents"]}
    codex_names = {
        path.stem for path in (REPO_ROOT / "plugins" / "kitty" / ".codex" / "agents").glob("*.toml")
    }

    assert source_names == manifest_names == codex_names


def test_agent_source_schema_has_required_contract_fields() -> None:
    source_dir = REPO_ROOT / "plugins" / "kitty" / "_source" / "agents"

    for path in source_dir.glob("*.yaml"):
        data = yaml.safe_load(path.read_text())
        assert data["name"] == path.stem
        assert data["role"] in {"annotation", "research", "review"}
        assert data["model"]
        assert data["tools"]
        assert "mcp_tools" in data
        assert data["developer_instructions"].startswith("# ")


def test_generated_codex_agent_toml_parses() -> None:
    codex_dir = REPO_ROOT / "plugins" / "kitty" / ".codex" / "agents"

    for path in codex_dir.glob("*.toml"):
        data = tomllib.loads(path.read_text())
        assert data["name"] == path.stem
        assert data["framework_status"] == "active-framework-agent"
        assert data["prompt"].startswith("# ")


def test_generated_manifest_json_parses() -> None:
    manifest_paths = [
        REPO_ROOT / "plugins" / "kitty" / ".claude-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "kitty" / ".codex-plugin" / "plugin.json",
        REPO_ROOT / ".codex-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "kitty" / "gemini-extension.json",
        REPO_ROOT / "plugins" / "kitty" / ".mcp.json",
        REPO_ROOT / "plugins" / "kitty" / "agents" / "manifest.json",
    ]

    for path in manifest_paths:
        assert json.loads(path.read_text())


def test_every_agent_uses_sonnet_unless_force_opus_is_set() -> None:
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        force_opus = data.get("force_opus", False)
        if force_opus:
            assert data.get("force_opus_reason"), (
                f"{path.name}: force_opus=true requires force_opus_reason"
            )
        else:
            assert data["model"] == "claude-sonnet-4-6", (
                f"{path.name}: default model must be claude-sonnet-4-6 unless force_opus is true"
            )


def test_tool_budgets_are_minimum_viable_per_role() -> None:
    """Annotator may keep Bash for git inspections; researchers/reviewers must not."""

    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        tools = set(data["tools"])
        if data["name"] in ANNOTATOR_NAMES:
            assert tools <= ANNOTATOR_TOOL_BUDGET, (
                f"{path.name}: tools {tools} exceed annotator budget {ANNOTATOR_TOOL_BUDGET}"
            )
        else:
            assert tools <= RESEARCH_REVIEW_TOOL_BUDGET, (
                f"{path.name}: research/review agents must not include Bash; got {tools}"
            )


def test_librarians_and_experts_share_mcp_tool_baseline() -> None:
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        name = data["name"]
        if name in ANNOTATOR_NAMES:
            assert set(data["mcp_tools"]) == {"query_node", "get_file_structure"}, (
                f"{path.name}: annotator mcp_tools should be exactly query_node + get_file_structure"
            )
        else:
            assert set(data["mcp_tools"]) == EXPECTED_LIBRARIAN_EXPERT_MCP_TOOLS, (
                f"{path.name}: librarians/experts must share the standard mcp_tool baseline"
            )


def test_research_and_review_agents_embed_scaling_rules() -> None:
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data["role"] in {"research", "review"}:
            assert "## Scaling" in data["developer_instructions"], (
                f"{path.name}: research/review agent prompt must contain a `## Scaling` section"
            )
            assert data["scaling_rules"], (
                f"{path.name}: research/review agent must populate scaling_rules metadata"
            )


def test_all_agents_declare_unified_output_contract() -> None:
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        contract = data["output_contract"]
        assert isinstance(contract, dict), f"{path.name}: output_contract must be a mapping"
        assert "schema" in contract, f"{path.name}: output_contract missing `schema`"
        assert "reference" in contract, f"{path.name}: output_contract missing `reference`"
        assert "agent-output-contract.md" in contract["reference"], (
            f"{path.name}: output_contract.reference must point to agent-output-contract.md"
        )


def test_force_opus_validation_in_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Direct in-process check that force_opus=true without a reason raises."""

    fake_source = tmp_path / "agents"
    fake_source.mkdir()
    bad_agent = {
        "name": "bad-agent",
        "description": "fixture",
        "role": "research",
        "model": "claude-opus-4-7",
        "tools": ["Read"],
        "mcp_tools": [],
        "force_opus": True,
        "developer_instructions": "# Bad Agent\n",
    }
    (fake_source / "bad-agent.yaml").write_text(
        yaml.safe_dump(bad_agent, sort_keys=False), encoding="utf-8"
    )

    sys.path.insert(0, str(REPO_ROOT))
    try:
        import scripts.generate_agents as gen

        monkeypatch.setattr(gen, "SOURCE_DIR", fake_source)
        with pytest.raises(ValueError, match="force_opus_reason"):
            gen._load_agent_sources()
    finally:
        sys.path.pop(0)
