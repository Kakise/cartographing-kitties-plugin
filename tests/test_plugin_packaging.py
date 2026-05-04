from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "plugins" / "kitty" / "skills"


def test_root_codex_plugin_manifest_paths_exist() -> None:
    manifest_path = REPO_ROOT / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())

    skills_path = REPO_ROOT / manifest["skills"]
    mcp_path = REPO_ROOT / manifest["mcpServers"]

    assert skills_path.exists()
    assert mcp_path.exists()

    codex_config = REPO_ROOT / "plugins" / "kitty" / ".codex" / "config.toml"
    assert codex_config.exists(), "missing plugins/kitty/.codex/config.toml"

    for skill_name in ("kitty-lfg", "kitty-work"):
        openai_yaml = SKILLS_ROOT / skill_name / "agents" / "openai.yaml"
        assert openai_yaml.exists(), (
            f"missing {openai_yaml.relative_to(REPO_ROOT)} — orchestrator skills must "
            f"declare an implicit-invocation policy for Codex"
        )


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


def test_agent_manifest_declares_all_generated_sources() -> None:
    agents_dir = REPO_ROOT / "plugins" / "kitty" / "agents"
    source_dir = REPO_ROOT / "plugins" / "kitty" / "_source" / "agents"
    codex_dir = REPO_ROOT / "plugins" / "kitty" / ".codex" / "agents"
    manifest = json.loads((agents_dir / "manifest.json").read_text())

    declared_names = {entry["name"] for entry in manifest["agents"]}
    source_names = {path.stem for path in source_dir.glob("*.yaml")}
    codex_names = {path.stem for path in codex_dir.glob("*.toml")}

    assert declared_names == source_names
    assert declared_names == codex_names


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


def test_generated_harness_artifacts_are_current() -> None:
    checks = [
        ["scripts/generate_agents.py", "--check"],
        ["scripts/generate_manifests.py", "--check"],
        ["scripts/generate_tool_reference.py", "--check"],
        ["scripts/validate_skills.py"],
    ]

    for command in checks:
        result = subprocess.run(
            [sys.executable, *command],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr


def test_memory_workflow_reference_exists() -> None:
    memory_reference = (
        REPO_ROOT / "plugins" / "kitty" / "skills" / "kitty" / "references" / "memory-workflow.md"
    )

    assert memory_reference.exists()
    text = memory_reference.read_text()
    assert "query_litter_box" in text
    assert "query_treat_box" in text
    assert "add_litter_box_entry" in text
    assert "add_treat_box_entry" in text


def test_workflow_skills_require_memory_preflight() -> None:
    skill_names = [
        "kitty-brainstorm",
        "kitty-plan",
        "kitty-work",
        "kitty-review",
        "kitty-lfg",
    ]

    for skill_name in skill_names:
        text = (REPO_ROOT / "plugins" / "kitty" / "skills" / skill_name / "SKILL.md").read_text()
        assert "query_litter_box" in text, skill_name
        assert "query_treat_box" in text, skill_name


def test_mutating_workflow_skills_require_memory_postflight() -> None:
    for skill_name in ["kitty-work", "kitty-review", "kitty-lfg"]:
        text = (REPO_ROOT / "plugins" / "kitty" / "skills" / skill_name / "SKILL.md").read_text()
        assert "add_litter_box_entry" in text, skill_name
        assert "add_treat_box_entry" in text, skill_name


def test_framework_agents_accept_memory_context() -> None:
    agents_dir = REPO_ROOT / "plugins" / "kitty" / "agents"
    for agent_path in agents_dir.glob("*.md"):
        text = agent_path.read_text()
        assert "Memory Context" in text or "memory_context" in text, agent_path.name


def test_skills_submodule_initialized() -> None:
    assert SKILLS_ROOT.exists(), (
        "plugins/kitty/skills is missing — run `git submodule update --init --recursive`"
    )
    skill_files = list(SKILLS_ROOT.glob("*/SKILL.md"))
    assert len(skill_files) >= 9, (
        f"expected at least 9 SKILL.md files under {SKILLS_ROOT}, found {len(skill_files)}"
    )


def _parse_skill_frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path}: missing frontmatter"
    end = text.find("\n---\n", 4)
    assert end != -1, f"{path}: frontmatter is not closed"
    data = yaml.safe_load(text[4:end]) or {}
    assert isinstance(data, dict), f"{path}: frontmatter must be a mapping"
    return data


def test_skill_frontmatter_declares_kitty_mcp_requirement() -> None:
    skill_files = sorted(SKILLS_ROOT.glob("*/SKILL.md"))
    assert skill_files, "no SKILL.md files found — submodule may be uninitialized"

    for path in skill_files:
        frontmatter = _parse_skill_frontmatter(path)

        description = frontmatter.get("description")
        assert isinstance(description, str), f"{path}: description must be a string"
        assert "Cartographing Kittens MCP server" in description, (
            f"{path}: description must mention `Cartographing Kittens MCP server`"
        )

        requires = frontmatter.get("requires")
        assert isinstance(requires, dict), f"{path}: requires must be a mapping"
        mcp_servers = requires.get("mcp_servers")
        assert isinstance(mcp_servers, list) and "kitty" in mcp_servers, (
            f"{path}: requires.mcp_servers must include `kitty`"
        )
