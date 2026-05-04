"""Tests for ``scripts/sync_claude_agents_md.py``.

The script enforces the section-level contract between ``CLAUDE.md`` and
``AGENTS.md``. These tests cover both the happy path (clean tree) and the
common drift modes (missing section, content drift in a non-allowlisted
section, content drift in an allowlisted section).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_claude_agents_md.py"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"


def _run_script(*extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_repository_tree_passes_check() -> None:
    result = _run_script("--check")
    assert result.returncode == 0, result.stderr


def test_check_fails_when_agents_md_drops_a_required_section(tmp_path: Path) -> None:
    claude_clone = tmp_path / "CLAUDE.md"
    agents_clone = tmp_path / "AGENTS.md"
    claude_clone.write_text(CLAUDE_MD.read_text(encoding="utf-8"), encoding="utf-8")

    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    target = "## Cartographing Kittens-First Principle"
    assert target in agents_text, "fixture assumption broken — section was renamed"

    sentinel = "## Sentinel After Removal"
    sliced_lines: list[str] = []
    skip = False
    for line in agents_text.splitlines():
        if line.startswith(target):
            skip = True
            sliced_lines.append(sentinel)
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            sliced_lines.append(line)
    agents_clone.write_text("\n".join(sliced_lines), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--check",
            "--claude",
            str(claude_clone),
            "--agents",
            str(agents_clone),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Cartographing Kittens-First Principle" in result.stderr


def test_check_fails_when_non_allowlisted_section_drifts(tmp_path: Path) -> None:
    claude_clone = tmp_path / "CLAUDE.md"
    agents_clone = tmp_path / "AGENTS.md"
    claude_clone.write_text(CLAUDE_MD.read_text(encoding="utf-8"), encoding="utf-8")

    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    drifted = agents_text.replace(
        "## Testing\n",
        "## Testing\n\nAdded line that is not present in CLAUDE.md.\n",
        1,
    )
    assert drifted != agents_text, "fixture assumption broken — Testing section heading missing"
    agents_clone.write_text(drifted, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--check",
            "--claude",
            str(claude_clone),
            "--agents",
            str(agents_clone),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "Testing" in result.stderr


def test_check_tolerates_drift_in_allowlisted_section(tmp_path: Path) -> None:
    claude_clone = tmp_path / "CLAUDE.md"
    agents_clone = tmp_path / "AGENTS.md"
    claude_clone.write_text(CLAUDE_MD.read_text(encoding="utf-8"), encoding="utf-8")

    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    drifted = agents_text.replace(
        "## MCP Server (local dev)\n",
        "## MCP Server (local dev)\n\nAdded Codex-only example that is allow-listed.\n",
        1,
    )
    assert drifted != agents_text, (
        "fixture assumption broken — MCP Server (local dev) heading missing"
    )
    agents_clone.write_text(drifted, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--check",
            "--claude",
            str(claude_clone),
            "--agents",
            str(agents_clone),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "section",
    [
        "Architecture",
        "Workflow Pipeline",
        "Agent Output Contracts",
        "Cartographing Kittens-First Principle",
        "Development",
        "Testing",
    ],
)
def test_required_sections_present_in_both(section: str) -> None:
    claude_text = CLAUDE_MD.read_text(encoding="utf-8")
    agents_text = AGENTS_MD.read_text(encoding="utf-8")
    heading = f"## {section}"
    assert heading in claude_text, f"CLAUDE.md missing {heading!r}"
    assert heading in agents_text, f"AGENTS.md missing {heading!r}"
