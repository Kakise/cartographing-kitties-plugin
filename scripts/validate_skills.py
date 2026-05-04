from __future__ import annotations

import argparse
import json
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
SKILLS_ROOT = REPO_ROOT / "plugins" / "kitty" / "skills"
MAX_SKILL_LINES = 500
KNOWN_TOOLS = {
    "annotation_status",
    "batch_query_nodes",
    "find_dependencies",
    "find_dependents",
    "find_stale_annotations",
    "get_context_summary",
    "get_file_structure",
    "get_pending_annotations",
    "graph_diff",
    "index_codebase",
    "query_litter_box",
    "query_node",
    "query_treat_box",
    "rank_nodes",
    "search",
    "submit_annotations",
    "validate_graph",
    "Read",
    "Grep",
    "Glob",
    "Bash",
    "Task",
    "Write",
    "Edit",
    "MultiEdit",
}


def _parse_frontmatter(path: Path) -> tuple[dict[str, Any], str, list[str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not text.startswith("---\n"):
        raise ValueError("missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("frontmatter is not closed")
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, text[end + len("\n---\n") :], lines


def _normalise_allowed_tools(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ValueError("allowed-tools must be a comma-separated string or list")


def _referenced_markdown_files(body: str) -> set[str]:
    references: set[str] = set()
    for token in body.replace("(", " ").replace(")", " ").replace("`", " ").split():
        if "references/" in token and token.endswith(".md"):
            references.add(token.strip(".,:;"))
    return references


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        frontmatter, body, lines = _parse_frontmatter(path)
    except ValueError as exc:
        return [f"{path.relative_to(REPO_ROOT)}: {exc}"]

    display = path.relative_to(REPO_ROOT)
    if len(lines) > MAX_SKILL_LINES:
        errors.append(f"{display}: {len(lines)} lines exceeds {MAX_SKILL_LINES}")

    for key in ("name", "description"):
        if key not in frontmatter:
            errors.append(f"{display}: frontmatter missing `{key}`")

    if "$ARGUMENTS" in body and "argument-hint" not in frontmatter:
        errors.append(f"{display}: references $ARGUMENTS but lacks `argument-hint`")

    for tool in _normalise_allowed_tools(frontmatter.get("allowed-tools")):
        base_tool = tool.split("__", 1)[-1] if "__" in tool else tool
        if base_tool not in KNOWN_TOOLS:
            errors.append(f"{display}: unknown allowed-tool `{tool}`")

    for reference in _referenced_markdown_files(body):
        candidates = [path.parent / reference]
        if reference.startswith("kitty/"):
            candidates.append(SKILLS_ROOT / reference)
        if reference.startswith("references/"):
            candidates.append(SKILLS_ROOT / "kitty" / reference)
        if not any(candidate.exists() for candidate in candidates):
            errors.append(f"{display}: missing referenced file `{reference}`")

    return errors


def _validate_kitty_router_spawn_map() -> list[str]:
    """Enforce: every agent in agents/manifest.json appears in kitty/SKILL.md spawn map."""

    router_path = SKILLS_ROOT / "kitty" / "SKILL.md"
    manifest_path = REPO_ROOT / "plugins" / "kitty" / "agents" / "manifest.json"
    if not router_path.exists() or not manifest_path.exists():
        return []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared_names = {entry["name"] for entry in manifest["agents"]}
    body = router_path.read_text(encoding="utf-8")
    if "## Agent Spawn Map" not in body:
        return [f"{router_path.relative_to(REPO_ROOT)}: missing `## Agent Spawn Map` section"]

    missing = sorted(name for name in declared_names if f"`{name}`" not in body)
    if missing:
        return [
            f"{router_path.relative_to(REPO_ROOT)}: spawn map does not reference "
            f"{', '.join(missing)} (declared in agents/manifest.json)"
        ]
    return []


def validate_all() -> list[str]:
    errors: list[str] = []
    for skill_path in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        errors.extend(validate_skill(skill_path))
    errors.extend(_validate_kitty_router_spawn_map())
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    errors = validate_all()
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
