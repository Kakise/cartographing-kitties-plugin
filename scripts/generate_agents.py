from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "plugins" / "kitty").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLUGIN_ROOT = REPO_ROOT / "plugins" / "kitty"
SOURCE_DIR = PLUGIN_ROOT / "_source" / "agents"
TEMPLATE_DIR = PLUGIN_ROOT / "_source" / "templates"
CLAUDE_AGENT_DIR = PLUGIN_ROOT / "agents"
CODEX_AGENT_DIR = PLUGIN_ROOT / ".codex" / "agents"
MANIFEST_PATH = CLAUDE_AGENT_DIR / "manifest.json"
SUBGRAPH_CONTEXT_POINTER = "plugins/kitty/skills/kitty/references/subgraph-context-format.md"


def _literal_presenter(dumper: yaml.Dumper, value: str) -> yaml.Node:
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


yaml.SafeDumper.add_representer(str, _literal_presenter)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open() as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, width=100, allow_unicode=True),
        encoding="utf-8",
    )


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
    return frontmatter, body


def _normalise_tools(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError(f"tools must be a string or list, got {type(value).__name__}")


def _toml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_agent_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        agent = _load_yaml(path)
        required = {
            "name",
            "description",
            "role",
            "model",
            "tools",
            "developer_instructions",
        }
        missing = sorted(required - agent.keys())
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
        agent["tools"] = _normalise_tools(agent["tools"])
        agent.setdefault("mcp_tools", [])
        agent.setdefault("color", None)
        agent.setdefault("framework_status", "active-framework-agent")
        agent.setdefault(
            "runtime_support",
            {
                "claude_code": "directory-discovered",
                "codex": "framework-declared-inline-first",
            },
        )
        agent.setdefault(
            "runtimes",
            {"claude_code": "directory-discovered", "codex": "framework-declared"},
        )
        agent.setdefault("expected_context_pointer", SUBGRAPH_CONTEXT_POINTER)
        sources.append(agent)
    if not sources:
        raise ValueError(f"No agent source files found in {SOURCE_DIR}")
    return sources


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["toml_string"] = _toml_string
    env.filters["json_array"] = lambda value: json.dumps(value, ensure_ascii=False)
    env.filters["description_lines"] = lambda value: textwrap.wrap(
        str(value).replace("\n", " "), width=88
    )
    return env


def render_outputs() -> dict[Path, str]:
    agents = _load_agent_sources()
    env = _environment()
    claude_template = env.get_template("agent.claude.md.j2")
    codex_template = env.get_template("agent.codex.toml.j2")
    manifest_template = env.get_template("manifest.agents.json.j2")

    outputs: dict[Path, str] = {}
    for agent in agents:
        outputs[CLAUDE_AGENT_DIR / f"{agent['name']}.md"] = claude_template.render(**agent)
        outputs[CODEX_AGENT_DIR / f"{agent['name']}.toml"] = codex_template.render(**agent)

    manifest = manifest_template.render(agents=agents)
    manifest = json.dumps(json.loads(manifest), indent=2, ensure_ascii=False) + "\n"
    outputs[MANIFEST_PATH] = manifest
    return outputs


def bootstrap_from_current() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_roles = {entry["name"]: entry["role"] for entry in manifest["agents"]}
    manifest_runtimes = {entry["name"]: entry["runtimes"] for entry in manifest["agents"]}

    for agent_path in sorted(CLAUDE_AGENT_DIR.glob("*.md")):
        frontmatter, body = _parse_frontmatter(agent_path)
        name = str(frontmatter["name"])
        source = {
            "name": name,
            "description": str(frontmatter["description"]).strip(),
            "role": manifest_roles.get(name, "research"),
            "model": str(frontmatter.get("model", "inherit")),
            "tools": _normalise_tools(frontmatter.get("tools")),
            "mcp_tools": [],
            "color": frontmatter.get("color"),
            "framework_status": frontmatter.get("framework_status", "active-framework-agent"),
            "runtime_support": frontmatter.get(
                "runtime_support",
                {
                    "claude_code": "directory-discovered",
                    "codex": "framework-declared-inline-first",
                },
            ),
            "runtimes": manifest_runtimes.get(
                name,
                {"claude_code": "directory-discovered", "codex": "framework-declared"},
            ),
            "output_contract": None,
            "scaling_rules": [],
            "expected_context_pointer": SUBGRAPH_CONTEXT_POINTER,
            "developer_instructions": body.rstrip() + "\n",
            "generated_from_sha256": _sha256(agent_path.read_text(encoding="utf-8")),
        }
        _write_yaml(SOURCE_DIR / f"{name}.yaml", source)


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
        print("Generated agent artifacts are out of date:", file=sys.stderr)
        for path in drifted:
            print(f"  - {path}", file=sys.stderr)
        print("Run `uv run python scripts/generate_agents.py`.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if outputs drift")
    parser.add_argument(
        "--bootstrap-from-current",
        action="store_true",
        help="seed _source/agents from the current generated Claude agent files",
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
