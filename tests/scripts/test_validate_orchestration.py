"""Unit tests for the orchestration-script validator helpers (plan Unit 2).

These functions are pure and unit-testable. `check_orch_prologue`, `check_no_scriptpath`,
and `check_orch_loc` are wired live in the validator's main pass (against production
`*.orch.js`); `check_entry_self_check` and `check_exact_roster` exist and are tested here
but are NOT yet enforced live (deferred to Units 6 and 4 respectively).
"""

from __future__ import annotations

from pathlib import Path

import scripts.validate_skills as validate_skills


def _write_orch(tmp_path: Path, name: str, contents: str) -> Path:
    path = tmp_path / name
    path.write_text(contents, encoding="utf-8")
    return path


# --- check_orch_prologue -------------------------------------------------------------

PROLOGUE_LINE = "const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})\n"


def test_orch_prologue_present_no_error(tmp_path: Path) -> None:
    path = _write_orch(tmp_path, "ok.orch.js", PROLOGUE_LINE + "return {}\n")
    assert validate_skills.check_orch_prologue(path) == []


def test_orch_prologue_missing_errors(tmp_path: Path) -> None:
    path = _write_orch(tmp_path, "bad.orch.js", "const A = args ?? {}\nreturn {}\n")
    errors = validate_skills.check_orch_prologue(path)
    assert len(errors) == 1
    assert "args prologue" in errors[0]


# --- check_no_scriptpath -------------------------------------------------------------


def test_no_scriptpath_clean_no_error(tmp_path: Path) -> None:
    contents = (
        "export const meta = { name: 'kitty-x', description: 'ok' }\n"
        + PROLOGUE_LINE
        + "const out = await Workflow({ items: A.items })\n"
        + "return out\n"
    )
    path = _write_orch(tmp_path, "clean.orch.js", contents)
    assert validate_skills.check_no_scriptpath(path) == []


def test_no_scriptpath_workflow_scriptpath_errors(tmp_path: Path) -> None:
    contents = PROLOGUE_LINE + "const out = await Workflow({\n  scriptPath: './x.js',\n})\n"
    path = _write_orch(tmp_path, "scriptpath.orch.js", contents)
    errors = validate_skills.check_no_scriptpath(path)
    assert len(errors) == 1
    assert "scriptPath:" in errors[0]


def test_no_scriptpath_workflow_name_errors(tmp_path: Path) -> None:
    contents = PROLOGUE_LINE + "const out = await Workflow({\n  name: 'kitty-x',\n})\n"
    path = _write_orch(tmp_path, "wfname.orch.js", contents)
    errors = validate_skills.check_no_scriptpath(path)
    assert len(errors) == 1
    assert "name:" in errors[0]


def test_no_scriptpath_meta_name_line_alone_no_error(tmp_path: Path) -> None:
    # A `name:` inside a `meta` object (not a Workflow() argument) is FINE.
    contents = PROLOGUE_LINE + "const meta = { name: 'x' }\nreturn meta\n"
    path = _write_orch(tmp_path, "meta.orch.js", contents)
    assert validate_skills.check_no_scriptpath(path) == []


def test_no_scriptpath_export_meta_name_no_error(tmp_path: Path) -> None:
    # The canonical export-meta-with-name shape (multi-line) must not trip the check.
    contents = (
        "export const meta = {\n"
        "  name: 'kitty-review',\n"
        "  description: 'review orchestration',\n"
        "}\n" + PROLOGUE_LINE + "return {}\n"
    )
    path = _write_orch(tmp_path, "exportmeta.orch.js", contents)
    assert validate_skills.check_no_scriptpath(path) == []


# --- check_orch_loc ------------------------------------------------------------------


def test_orch_loc_under_limit_no_error(tmp_path: Path) -> None:
    path = _write_orch(tmp_path, "small.orch.js", "\n".join(["x"] * 50) + "\n")
    assert validate_skills.check_orch_loc(path) == []


def test_orch_loc_over_limit_errors(tmp_path: Path) -> None:
    path = _write_orch(tmp_path, "big.orch.js", "\n".join(["x"] * 201) + "\n")
    errors = validate_skills.check_orch_loc(path)
    assert len(errors) == 1
    assert "exceeds orchestration cap 200" in errors[0]


def test_orch_loc_custom_limit(tmp_path: Path) -> None:
    path = _write_orch(tmp_path, "lim.orch.js", "\n".join(["x"] * 11) + "\n")
    assert validate_skills.check_orch_loc(path, limit=20) == []
    assert validate_skills.check_orch_loc(path, limit=10) != []


# --- check_entry_self_check ----------------------------------------------------------


def test_entry_self_check_required_absent_errors() -> None:
    errors = validate_skills.check_entry_self_check("no marker here\n", required=True)
    assert len(errors) == 1
    assert "entry self-check sentinel" in errors[0]


def test_entry_self_check_required_present_no_error() -> None:
    body = "preamble\n<!-- entry-self-check -->\nmore\n"
    assert validate_skills.check_entry_self_check(body, required=True) == []


def test_entry_self_check_not_required_no_error() -> None:
    assert validate_skills.check_entry_self_check("no marker\n", required=False) == []


# --- check_exact_roster --------------------------------------------------------------

EXPECTED_SEVEN = {
    "librarian-kitten",
    "expert-kitten-correctness",
    "expert-kitten-testing",
    "expert-kitten-impact",
    "expert-kitten-structure",
    "expert-kitten-context",
    "cartographing-kitten",
}


def test_exact_roster_matches_no_error() -> None:
    assert validate_skills.check_exact_roster(sorted(EXPECTED_SEVEN), EXPECTED_SEVEN) == []


def test_exact_roster_six_errors() -> None:
    six = sorted(EXPECTED_SEVEN - {"cartographing-kitten"})
    errors = validate_skills.check_exact_roster(six, EXPECTED_SEVEN)
    assert len(errors) == 1
    assert "missing cartographing-kitten" in errors[0]


def test_exact_roster_eight_errors() -> None:
    eight = sorted(EXPECTED_SEVEN | {"librarian-kitten-flow"})
    errors = validate_skills.check_exact_roster(eight, EXPECTED_SEVEN)
    assert len(errors) == 1
    assert "unexpected librarian-kitten-flow" in errors[0]


def test_exact_roster_module_constant_matches_expected() -> None:
    # The validator ships the same 7-set the future live wiring (Unit 4) enforces.
    assert set(validate_skills.EXPECTED_AGENT_ROSTER) == EXPECTED_SEVEN
