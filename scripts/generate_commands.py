from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "plugins" / "kitty").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLUGIN_ROOT = REPO_ROOT / "plugins" / "kitty"
SOURCE_DIR = PLUGIN_ROOT / "_source" / "commands"
CLAUDE_COMMAND_DIR = PLUGIN_ROOT / "commands"
CODEX_PROMPT_DIR = PLUGIN_ROOT / "prompts"


def _literal_presenter(dumper: yaml.Dumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


yaml.SafeDumper.add_representer(str, _literal_presenter)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, width=100, allow_unicode=True)


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} is missing frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path} frontmatter is not closed")
    frontmatter = yaml.safe_load(text[4:end]) or {}
    body = text[end + len("\n---\n") :].lstrip("\n")
    if not isinstance(frontmatter, dict):
        raise ValueError(f"{path} frontmatter must be a mapping")
    return frontmatter, body.rstrip() + "\n"


def _load_command_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        source = _load_yaml(path)
        required = {"name", "description", "claude", "codex_prompt"}
        missing = sorted(required - source.keys())
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
        if path.stem != source["name"]:
            raise ValueError(f"{path}: file stem must match command name {source['name']!r}")
        claude = source["claude"]
        if not isinstance(claude, dict) or not isinstance(claude.get("body"), str):
            raise ValueError(f"{path}: claude.body must be a string")
        if not isinstance(source["codex_prompt"], str) or not source["codex_prompt"].strip():
            raise ValueError(f"{path}: codex_prompt must be a non-empty string")
        sources.append(source)
    if not sources:
        raise ValueError(f"No command source files found in {SOURCE_DIR}")
    return sources


def _render_claude_command(source: dict[str, Any]) -> str:
    claude = source["claude"]
    frontmatter: dict[str, Any] = {"description": source["description"]}
    if claude.get("argument_hint"):
        frontmatter["argument-hint"] = claude["argument_hint"]
    if claude.get("allowed_tools"):
        allowed_tools = claude["allowed_tools"]
        if isinstance(allowed_tools, list):
            frontmatter["allowed-tools"] = ", ".join(str(tool) for tool in allowed_tools)
        else:
            frontmatter["allowed-tools"] = str(allowed_tools)
    body = str(claude["body"]).rstrip() + "\n"
    return f"---\n{_dump_yaml(frontmatter)}---\n\n{body}"


def render_outputs() -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for source in _load_command_sources():
        name = str(source["name"])
        outputs[CLAUDE_COMMAND_DIR / f"{name}.md"] = _render_claude_command(source)
        outputs[CODEX_PROMPT_DIR / f"{name}.md"] = str(source["codex_prompt"]).rstrip() + "\n"
    return outputs


def bootstrap_from_current() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for command_path in sorted(CLAUDE_COMMAND_DIR.glob("*.md")):
        frontmatter, body = _parse_frontmatter(command_path)
        prompt_path = CODEX_PROMPT_DIR / command_path.name
        source = {
            "name": command_path.stem,
            "description": frontmatter["description"],
            "claude": {
                "argument_hint": frontmatter.get("argument-hint"),
                "allowed_tools": frontmatter.get("allowed-tools"),
                "body": body,
            },
            "codex_prompt": prompt_path.read_text(encoding="utf-8")
            if prompt_path.exists()
            else body,
        }
        (SOURCE_DIR / f"{command_path.stem}.yaml").write_text(_dump_yaml(source), encoding="utf-8")


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> int:
    drifted: list[Path] = []
    for path, expected in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drifted.append(path.relative_to(REPO_ROOT))
    if drifted:
        print("Generated command artifacts are out of date:", file=sys.stderr)
        for path in drifted:
            print(f"  - {path}", file=sys.stderr)
        print("Run `uv run python scripts/generate_commands.py`.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if outputs drift")
    parser.add_argument(
        "--bootstrap-from-current",
        action="store_true",
        help="seed _source/commands from the current generated command files",
    )
    args = parser.parse_args(argv)

    if args.bootstrap_from_current:
        bootstrap_from_current()
        return 0

    outputs = render_outputs()
    if args.check:
        return check_outputs(outputs)
    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
