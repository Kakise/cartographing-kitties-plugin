"""Codex parity assertions.

Every framework subagent declared in ``plugins/kitty/agents/manifest.json``
must have a Codex-flavored TOML twin under ``plugins/kitty/.codex/agents/``.
The Codex runtime defaults file (``.codex/config.toml``) and the per-skill
implicit-invocation policy files (``agents/openai.yaml``) are part of the same
parity contract — together they let Codex execute the framework without
losing context relative to Claude Code.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
KITTY_ROOT = REPO_ROOT / "plugins" / "kitty"
AGENTS_DIR = KITTY_ROOT / "agents"
CODEX_AGENTS_DIR = KITTY_ROOT / ".codex" / "agents"
CODEX_CONFIG_PATH = KITTY_ROOT / ".codex" / "config.toml"
SKILLS_ROOT = KITTY_ROOT / "skills"

# Skills whose orchestrator semantics make implicit Codex invocation unsafe.
ORCHESTRATOR_SKILLS = ("kitty-work", "kitty-lfg")


def test_every_manifest_agent_has_a_codex_toml() -> None:
    manifest = json.loads((AGENTS_DIR / "manifest.json").read_text())
    declared_names = {entry["name"] for entry in manifest["agents"]}
    actual_codex_names = {path.stem for path in CODEX_AGENTS_DIR.glob("*.toml")}

    assert declared_names == actual_codex_names, (
        f"declared={sorted(declared_names)} codex={sorted(actual_codex_names)}"
    )


def test_codex_config_toml_parses_with_required_keys() -> None:
    assert CODEX_CONFIG_PATH.exists(), f"missing {CODEX_CONFIG_PATH.relative_to(REPO_ROOT)}"
    config = tomllib.loads(CODEX_CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["max_threads"] == 4
    assert config["max_depth"] == 1
    assert config["job_max_runtime_seconds"] == 300


def test_codex_agent_tomls_parse() -> None:
    for path in sorted(CODEX_AGENTS_DIR.glob("*.toml")):
        try:
            tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise AssertionError(f"{path.relative_to(REPO_ROOT)} failed to parse: {exc}") from exc


def test_orchestrator_skills_ship_openai_yaml() -> None:
    for skill_name in ORCHESTRATOR_SKILLS:
        path = SKILLS_ROOT / skill_name / "agents" / "openai.yaml"
        assert path.exists(), f"missing {path.relative_to(REPO_ROOT)}"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{path.name}: expected mapping, got {type(data).__name__}"
        assert data.get("allow_implicit_invocation") is False, (
            f"{path.name}: allow_implicit_invocation must be False"
        )
        assert data.get("category") == "developer-tools", (
            f"{path.name}: category must be 'developer-tools'"
        )
