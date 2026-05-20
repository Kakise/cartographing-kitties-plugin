from __future__ import annotations

import argparse
import json
import re
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
# Limits from https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
MAX_DESCRIPTION_CHARS = 1024
MAX_WHEN_TO_USE_CHARS = 1024
# https://code.claude.com/docs/en/skills — `name` is lowercase letters, numbers, hyphens, ≤64.
NAME_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
# Plugin prefix Claude Code applies to MCP tools served by `plugins/kitty` for server `kitty`.
MCP_PREFIX = "mcp__plugin_kitty_kitty__"
KITTY_MCP_TOOLS = frozenset(
    {
        "add_litter_box_entry",
        "add_treat_box_entry",
        "annotation_status",
        "batch_query_nodes",
        "find_dependencies",
        "find_dependents",
        "find_low_quality_annotations",
        "find_stale_annotations",
        "get_agent_handoff",
        "get_context_summary",
        "get_file_structure",
        "get_pending_annotations",
        "graph_diff",
        "index_codebase",
        "query_litter_box",
        "query_node",
        "query_treat_box",
        "rank_nodes",
        "requeue_low_quality_annotations",
        "search",
        "submit_annotations",
        "validate_graph",
    }
)
BUILTIN_TOOLS = frozenset({"Read", "Grep", "Glob", "Bash", "Task", "Write", "Edit", "MultiEdit"})
KNOWN_TOOLS: frozenset[str] = frozenset(
    KITTY_MCP_TOOLS | {f"{MCP_PREFIX}{tool}" for tool in KITTY_MCP_TOOLS} | BUILTIN_TOOLS
)


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


def _display_path(path: Path) -> Path | str:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        frontmatter, body, lines = _parse_frontmatter(path)
    except ValueError as exc:
        return [f"{_display_path(path)}: {exc}"]

    display = _display_path(path)
    if len(lines) > MAX_SKILL_LINES:
        errors.append(f"{display}: {len(lines)} lines exceeds {MAX_SKILL_LINES}")

    for key in ("name", "description"):
        value = frontmatter.get(key)
        if not (isinstance(value, str) and value.strip()):
            # Catches both missing-key and empty-string ("must be non-empty" per spec).
            errors.append(f"{display}: frontmatter missing or empty `{key}`")

    name = frontmatter.get("name")
    if isinstance(name, str) and name and not NAME_PATTERN.match(name):
        errors.append(
            f"{display}: name `{name}` must match {NAME_PATTERN.pattern} "
            f"(lowercase letters, numbers, hyphens; the plugin namespace prefix is "
            f"added automatically by Claude Code)"
        )

    # Strip YAML literal-block trailing newlines before length-checking so we measure
    # payload, not YAML serialization (a `description: |\n  …\n` block always carries
    # a trailing newline).
    description = frontmatter.get("description", "")
    if isinstance(description, str):
        payload = description.rstrip()
        if len(payload) > MAX_DESCRIPTION_CHARS:
            errors.append(
                f"{display}: description length {len(payload)} exceeds {MAX_DESCRIPTION_CHARS}"
            )

    when_to_use = frontmatter.get("when_to_use", "")
    if isinstance(when_to_use, str):
        payload = when_to_use.rstrip()
        if len(payload) > MAX_WHEN_TO_USE_CHARS:
            errors.append(
                f"{display}: when_to_use length {len(payload)} exceeds {MAX_WHEN_TO_USE_CHARS}"
            )

    if "$ARGUMENTS" in body and "argument-hint" not in frontmatter:
        errors.append(f"{display}: references $ARGUMENTS but lacks `argument-hint`")

    for tool in _normalise_allowed_tools(frontmatter.get("allowed-tools")):
        if tool.startswith("mcp__") and not tool.startswith(MCP_PREFIX):
            errors.append(
                f"{display}: MCP tool `{tool}` must use prefix `{MCP_PREFIX}` "
                f"(plugin `kitty`, server `kitty`)"
            )
        if tool not in KNOWN_TOOLS:
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
