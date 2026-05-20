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
SOURCE_DIR = PLUGIN_ROOT / "_source" / "skills"
SKILLS_ROOT = PLUGIN_ROOT / "skills"


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


def _skill_dir_name(frontmatter: dict[str, Any]) -> str:
    name = str(frontmatter["name"])
    return name.replace(":", "-")


def _load_skill_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for path in sorted(SOURCE_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        source = _load_yaml(path)
        required = {"directory", "frontmatter", "body"}
        missing = sorted(required - source.keys())
        if missing:
            raise ValueError(f"{path} missing required keys: {', '.join(missing)}")
        frontmatter = source["frontmatter"]
        if not isinstance(frontmatter, dict):
            raise ValueError(f"{path}: frontmatter must be a mapping")
        for key in ("name", "description"):
            if key not in frontmatter:
                raise ValueError(f"{path}: frontmatter missing {key!r}")
        if not isinstance(source["body"], str) or not source["body"].strip():
            raise ValueError(f"{path}: body must be a non-empty string")
        sources.append(source)
    if not sources:
        raise ValueError(f"No skill source files found in {SOURCE_DIR}")
    return sources


def _render_skill(source: dict[str, Any]) -> str:
    frontmatter = dict(source["frontmatter"])
    body = str(source["body"]).rstrip() + "\n"
    return f"---\n{_dump_yaml(frontmatter)}---\n\n{body}"


def render_outputs() -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for source in _load_skill_sources():
        directory = str(source["directory"])
        outputs[SKILLS_ROOT / directory / "SKILL.md"] = _render_skill(source)
        agents = source.get("agents") or {}
        if not isinstance(agents, dict):
            raise ValueError(f"{SOURCE_DIR / (directory + '.yaml')}: agents must be a mapping")
        for runtime_name, runtime_config in sorted(agents.items()):
            if not isinstance(runtime_config, dict):
                raise ValueError(f"{directory}: agents.{runtime_name} must be a mapping")
            outputs[SKILLS_ROOT / directory / "agents" / f"{runtime_name}.yaml"] = _dump_yaml(
                runtime_config
            )
    return outputs


def bootstrap_from_current() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    for skill_path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        frontmatter, body = _parse_frontmatter(skill_path)
        source: dict[str, Any] = {
            "directory": skill_path.parent.name,
            "frontmatter": frontmatter,
            "body": body,
        }
        agents_dir = skill_path.parent / "agents"
        if agents_dir.exists():
            agents: dict[str, Any] = {}
            for policy_path in sorted(agents_dir.glob("*.yaml")):
                agents[policy_path.stem] = _load_yaml(policy_path)
            if agents:
                source["agents"] = agents
        target = SOURCE_DIR / f"{skill_path.parent.name}.yaml"
        target.write_text(_dump_yaml(source), encoding="utf-8")


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
        print("Generated skill artifacts are out of date:", file=sys.stderr)
        for path in drifted:
            print(f"  - {path}", file=sys.stderr)
        print("Run `uv run python scripts/generate_skills.py`.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if outputs drift")
    parser.add_argument(
        "--bootstrap-from-current",
        action="store_true",
        help="seed _source/skills from the current generated skill files",
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
