from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.validate_skills as validate_skills


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_skill_validator_script_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_skills.py"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_all_skill_spines_fit_line_budget() -> None:
    for skill_path in sorted((REPO_ROOT / "plugins" / "kitty" / "skills").glob("*/SKILL.md")):
        line_count = len(skill_path.read_text().splitlines())
        assert line_count <= validate_skills.MAX_SKILL_LINES, skill_path
