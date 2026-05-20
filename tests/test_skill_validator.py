from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import scripts.validate_skills as validate_skills

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_skill(directory: Path, frontmatter: str, body: str = "Body.\n") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    skill_path = directory / "SKILL.md"
    skill_path.write_text(f"---\n{frontmatter.strip()}\n---\n\n{body}", encoding="utf-8")
    return skill_path


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


def test_validates_name_format_rejects_colon(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        "name: kitty:plan\ndescription: example\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert any("must match" in err for err in errors), errors


def test_validates_name_format_accepts_lowercase_hyphens(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        "name: kitty-plan\ndescription: example\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert not any("must match" in err for err in errors), errors


def test_validates_description_length(tmp_path: Path) -> None:
    long_description = "x" * (validate_skills.MAX_DESCRIPTION_CHARS + 10)
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        f"name: kitty-plan\ndescription: {long_description}\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert any("description length" in err for err in errors), errors


def test_validates_when_to_use_length(tmp_path: Path) -> None:
    long_text = "y" * (validate_skills.MAX_WHEN_TO_USE_CHARS + 10)
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        f"name: kitty-plan\ndescription: ok\nwhen_to_use: {long_text}\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert any("when_to_use length" in err for err in errors), errors


def test_validates_mcp_prefix_rejects_wrong_prefix(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        "name: kitty-plan\ndescription: ok\nallowed-tools:\n- mcp__kitty__query_node\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert any("must use prefix" in err for err in errors), errors


def test_validates_mcp_prefix_accepts_correct_prefix(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        (
            "name: kitty-plan\ndescription: ok\nallowed-tools:\n"
            "- mcp__plugin_kitty_kitty__query_node\n"
        ),
    )
    errors = validate_skills.validate_skill(skill_path)
    assert not any("must use prefix" in err for err in errors), errors


def test_validates_description_empty_string_rejected(tmp_path: Path) -> None:
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        "name: kitty-plan\ndescription: ''\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert any("missing or empty `description`" in err for err in errors), errors


def test_validates_description_trailing_newline_stripped(tmp_path: Path) -> None:
    """Descriptions written with `|` literal blocks get a trailing newline from PyYAML.
    The length check must compare payload, not serialization, so a description of
    exactly MAX_DESCRIPTION_CHARS bytes followed by a newline must still pass.
    """
    payload = "x" * validate_skills.MAX_DESCRIPTION_CHARS
    skill_path = _write_skill(
        tmp_path / "kitty-plan",
        f"name: kitty-plan\ndescription: |\n  {payload}\n",
    )
    errors = validate_skills.validate_skill(skill_path)
    assert not any("description length" in err for err in errors), errors
