"""Drift checker for ``CLAUDE.md`` and ``AGENTS.md``.

Both files share a section structure. This script tokenises each into
H2-bounded sections and asserts:

1. The set of H2 section titles is equal between the two files.
2. For every section *not* in :data:`CONTENT_ALLOWLIST`, the body is identical.
   Sections in the allow-list may diverge in content (Codex-specific examples,
   runtime-specific paths) but must still appear under the same heading.

The script is informational — it does not regenerate either file. ``AGENTS.md``
remains hand-authored so Codex-flavored prose can stay idiomatic. ``--check``
mode is what pre-commit and CI run.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator
from pathlib import Path

CLAUDE_PATH_DEFAULT = "CLAUDE.md"
AGENTS_PATH_DEFAULT = "AGENTS.md"

# Section titles whose bodies are intentionally allowed to differ between
# CLAUDE.md and AGENTS.md. Both files must still use the same H2 title.
CONTENT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "Conventions",
        "Plugin Structure (Marketplace Layout)",
        "MCP Tool Surface",
        "MCP Server (local dev)",
    }
)


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()


def _iter_h2(text: str) -> Iterator[tuple[str, str]]:
    """Yield (title, body) pairs for each ``## Title`` block in ``text``.

    Headings inside fenced code blocks are ignored.
    """

    lines = text.splitlines()
    in_fence = False
    current_title: str | None = None
    current_body: list[str] = []

    def _flush() -> Iterator[tuple[str, str]]:
        if current_title is not None:
            yield current_title, "\n".join(current_body).rstrip() + "\n"

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if current_title is not None:
                current_body.append(line)
            continue
        if not in_fence and line.startswith("## ") and not line.startswith("### "):
            yield from _flush()
            current_title = line[3:].strip()
            current_body = []
            continue
        if current_title is not None:
            current_body.append(line)

    yield from _flush()


def parse_sections(path: Path) -> dict[str, str]:
    """Parse ``path`` into a mapping of H2 title → body string."""

    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    return dict(_iter_h2(path.read_text(encoding="utf-8")))


def diff_sections(
    claude_sections: dict[str, str],
    agents_sections: dict[str, str],
    *,
    allowlist: frozenset[str] = CONTENT_ALLOWLIST,
) -> list[str]:
    """Return a list of human-readable drift messages. Empty list = no drift."""

    errors: list[str] = []

    claude_titles = set(claude_sections)
    agents_titles = set(agents_sections)

    for missing in sorted(claude_titles - agents_titles):
        errors.append(f"AGENTS.md is missing the section '## {missing}' (present in CLAUDE.md)")
    for missing in sorted(agents_titles - claude_titles):
        errors.append(f"CLAUDE.md is missing the section '## {missing}' (present in AGENTS.md)")

    for title in sorted(claude_titles & agents_titles):
        if title in allowlist:
            continue
        if claude_sections[title] != agents_sections[title]:
            errors.append(
                f"Section '## {title}' content differs between CLAUDE.md and AGENTS.md "
                f"and is not in the content allow-list. "
                f"Either align the two files or add '{title}' to CONTENT_ALLOWLIST in "
                f"scripts/sync_claude_agents_md.py."
            )

    return errors


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--claude",
        default=str(REPO_ROOT / CLAUDE_PATH_DEFAULT),
        help="Path to CLAUDE.md (default: <repo>/CLAUDE.md).",
    )
    parser.add_argument(
        "--agents",
        default=str(REPO_ROOT / AGENTS_PATH_DEFAULT),
        help="Path to AGENTS.md (default: <repo>/AGENTS.md).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero on drift. Default behavior also exits non-zero on drift, but "
        "without --check the script prints a friendly success line on a clean tree.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    claude_path = Path(args.claude)
    agents_path = Path(args.agents)

    try:
        claude_sections = parse_sections(claude_path)
        agents_sections = parse_sections(agents_path)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    errors = diff_sections(claude_sections, agents_sections)
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1

    if not args.check:
        print(
            f"CLAUDE.md and AGENTS.md are in sync "
            f"({len(claude_sections)} sections, "
            f"{len(CONTENT_ALLOWLIST)} allow-listed for content drift)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
