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
MCP_PREFIX = "mcp__plugin_kitty_kitty__"
RESEARCH_REVIEW_BUILTIN_TOOL_BUDGET = {"Read", "Grep", "Glob"}
ANNOTATOR_BUILTIN_TOOL_BUDGET = {"Read", "Grep", "Glob", "Bash"}


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


def test_skill_generator_check_is_clean() -> None:
    result = _run_script("scripts/generate_skills.py", "--check")

    assert result.returncode == 0, result.stderr


def test_command_generator_check_is_clean() -> None:
    result = _run_script("scripts/generate_commands.py", "--check")

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
        assert data["claude_model"]
        assert "model" not in data
        assert data["tools"]
        # `mcp_tools` was a custom field Claude Code ignored; MCP tools now live in
        # `tools:` with the `mcp__plugin_kitty_kitty__` prefix per spec.
        assert "mcp_tools" not in data
        assert data["developer_instructions"].startswith("# ")


def test_generated_codex_agent_toml_parses() -> None:
    codex_dir = REPO_ROOT / "plugins" / "kitty" / ".codex" / "agents"

    for path in codex_dir.glob("*.toml"):
        data = tomllib.loads(path.read_text())
        assert data["name"] == path.stem
        assert set(data) == {"name", "description", "developer_instructions"}
        assert data["developer_instructions"].startswith("# ")
        assert "prompt" not in data
        assert "model" not in data


def test_skill_sources_drive_skill_outputs() -> None:
    source_dir = REPO_ROOT / "plugins" / "kitty" / "_source" / "skills"
    output_dir = REPO_ROOT / "plugins" / "kitty" / "skills"
    source_dirs = {
        yaml.safe_load(path.read_text())["directory"] for path in source_dir.glob("*.yaml")
    }
    output_dirs = {path.parent.name for path in output_dir.glob("*/SKILL.md")}

    assert source_dirs == output_dirs


def test_command_sources_drive_claude_and_codex_outputs() -> None:
    source_dir = REPO_ROOT / "plugins" / "kitty" / "_source" / "commands"
    command_dir = REPO_ROOT / "plugins" / "kitty" / "commands"
    prompt_dir = REPO_ROOT / "plugins" / "kitty" / "prompts"
    source_names = {path.stem for path in source_dir.glob("*.yaml")}
    claude_names = {path.stem for path in command_dir.glob("*.md")}
    codex_names = {path.stem for path in prompt_dir.glob("*.md")}

    assert source_names == claude_names == codex_names
    assert not list(command_dir.glob("*.toml"))


def test_install_codex_assets_supports_delete_old(tmp_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from scripts.install_codex_assets import install

        old_agent_dir = tmp_path / ".codex" / "agents"
        old_skill_dir = tmp_path / "skills" / "kitty"
        old_prompt_dir = tmp_path / "prompts"
        old_agent_dir.mkdir(parents=True)
        old_skill_dir.mkdir(parents=True)
        old_prompt_dir.mkdir(parents=True)
        (old_agent_dir / "librarian-kitten.toml").write_text("old")
        (old_skill_dir / "SKILL.md").write_text("old")
        (old_prompt_dir / "kitty-index.md").write_text("old")
        (old_prompt_dir / "unrelated.md").write_text("keep")

        result = install(tmp_path, layout_name="auto", delete_old=True)

        assert result["deleted"] >= 3
        assert (old_agent_dir / "librarian-kitten.toml").read_text() != "old"
        assert (old_skill_dir / "SKILL.md").read_text() != "old"
        assert (old_prompt_dir / "kitty-index.md").read_text() != "old"
        assert (old_prompt_dir / "unrelated.md").read_text() == "keep"
    finally:
        sys.path.pop(0)


def test_generated_manifest_json_parses() -> None:
    manifest_paths = [
        REPO_ROOT / "plugins" / "kitty" / ".claude-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "kitty" / ".codex-plugin" / "plugin.json",
        REPO_ROOT / ".codex-plugin" / "plugin.json",
        REPO_ROOT / "plugins" / "kitty" / ".mcp.json",
        REPO_ROOT / "plugins" / "kitty" / "agents" / "manifest.json",
    ]

    for path in manifest_paths:
        assert json.loads(path.read_text())


def test_every_claude_agent_uses_sonnet_by_default() -> None:
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["claude_model"] == "claude-sonnet-4-6"


def test_tool_budgets_are_minimum_viable_per_role() -> None:
    """Annotator may keep Bash for git inspections; researchers/reviewers must not.

    Per the Claude Code spec, MCP tools that the agent uses live in `tools:` with
    the `mcp__plugin_kitty_kitty__` prefix. The budget check applies to the
    built-in tools only — MCP tools are inspected separately by
    test_librarians_and_experts_share_mcp_tool_baseline.
    """

    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        builtin_tools = {t for t in data["tools"] if not t.startswith("mcp__")}
        if data["name"] in ANNOTATOR_NAMES:
            assert builtin_tools <= ANNOTATOR_BUILTIN_TOOL_BUDGET, (
                f"{path.name}: built-in tools {builtin_tools} "
                f"exceed annotator budget {ANNOTATOR_BUILTIN_TOOL_BUDGET}"
            )
        else:
            assert builtin_tools <= RESEARCH_REVIEW_BUILTIN_TOOL_BUDGET, (
                f"{path.name}: research/review agents must not include Bash; "
                f"got built-in tools {builtin_tools}"
            )


def test_all_agents_are_mcp_free() -> None:
    """Every framework agent is MCP-free — it reads a Context Bundle, never the graph.

    The orchestrator gathers all structural intelligence via MCP and distills it into
    the bundle; agents only `Read` that bundle (plus targeted source lines). No agent —
    researcher, reviewer, or annotator — may list an `mcp__` tool.
    """

    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        mcp_tools = {t for t in data["tools"] if t.startswith(MCP_PREFIX)}
        assert mcp_tools == set(), (
            f"{path.name}: agents are MCP-free; remove {sorted(mcp_tools)} from tools"
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


def test_agent_source_requires_claude_model_in_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Direct in-process check that agent source names Claude-only model metadata."""

    fake_source = tmp_path / "agents"
    fake_source.mkdir()
    bad_agent = {
        "name": "bad-agent",
        "description": "fixture",
        "role": "research",
        "tools": ["Read"],
        "mcp_tools": [],
        "developer_instructions": "# Bad Agent\n",
    }
    (fake_source / "bad-agent.yaml").write_text(
        yaml.safe_dump(bad_agent, sort_keys=False), encoding="utf-8"
    )

    sys.path.insert(0, str(REPO_ROOT))
    try:
        import scripts.generate_agents as gen

        monkeypatch.setattr(gen, "SOURCE_DIR", fake_source)
        with pytest.raises(ValueError, match="claude_model"):
            gen._load_agent_sources()
    finally:
        sys.path.pop(0)


def test_all_agent_colors_match_claude_code_spec() -> None:
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import scripts.generate_agents as gen
    finally:
        sys.path.pop(0)

    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        color = data.get("color")
        if color is None:
            continue
        assert color in gen.VALID_AGENT_COLORS, (
            f"{path.name}: color `{color}` is not in the Claude Code spec set "
            f"{sorted(gen.VALID_AGENT_COLORS)}"
        )


def test_agent_color_validator_rejects_unsupported_color(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_source = tmp_path / "agents"
    fake_source.mkdir()
    bad_agent = {
        "name": "bad-agent",
        "description": "fixture",
        "role": "research",
        "claude_model": "claude-sonnet-4-6",
        "tools": ["Read"],
        "color": "magenta",
        "developer_instructions": "# Bad Agent\n",
    }
    (fake_source / "bad-agent.yaml").write_text(
        yaml.safe_dump(bad_agent, sort_keys=False), encoding="utf-8"
    )

    sys.path.insert(0, str(REPO_ROOT))
    try:
        import scripts.generate_agents as gen

        monkeypatch.setattr(gen, "SOURCE_DIR", fake_source)
        with pytest.raises(ValueError, match="color `magenta`"):
            gen._load_agent_sources()
    finally:
        sys.path.pop(0)
