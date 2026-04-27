from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


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
        path.stem
        for path in (REPO_ROOT / "plugins" / "kitty" / ".codex" / "agents").glob("*.toml")
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
