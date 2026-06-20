"""CI harness for shipped orchestration scripts (`*.orch.js`) — spec §11/§16.

Two layers per script (basenames starting with `_` are one-off probes, skipped):

STATIC (always, no node needed)
  - the args prologue substring is present (#68969);
  - no `scriptPath:`/`name:` used as a `Workflow(...)` argument key (F2) — a `name:`
    inside the script's own `meta = {...}` literal is allowed;
  - ≤ 200 physical lines (the orchestration cap);
  - the script exports `meta`.

BEHAVIORAL (node, skipped with a reason if `node` is missing)
  A small `.mjs` runner (tests/fixtures/orch/runner.mjs) stubs the workflow globals
  (agent/parallel/pipeline/phase/log/args/budget), wraps the script body in an async
  function, runs it against the fixture bundle, and prints a JSON report. We assert:
    (a) a NORMAL run (agent returns valid stub objects) completes without throwing and
        returns a result;
    (b) FAULT runs — the stubbed agent THROWS / returns null / returns schema-invalid for
        ONE item — each record that item as `failed` in the returned ledger (or in a
        `failed`/gate list), never silently drop it, and never crash the run.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / "plugins" / "kitty" / "skills" / "kitty" / "references" / "workflows"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "orch"
RUNNER = FIXTURE_DIR / "runner.mjs"
BUNDLE = FIXTURE_DIR / "bundle.md"

ARGS_PROLOGUE = "typeof args === 'string' ? JSON.parse(args)"
MAX_ORCH_LINES = 200
NODE = shutil.which("node")

# Mirror of validate_skills.check_no_scriptpath: find each `Workflow(` call, walk to its
# matching close paren, and reject a `scriptPath:`/`name:` key inside that region.
_WORKFLOW_CALL_RE = re.compile(r"Workflow\s*\(")
_FORBIDDEN_KEY_RE = re.compile(r"(?m)^\s*(scriptPath|name)\s*:")


def _balanced_region(text: str, open_paren_index: int) -> str:
    depth = 0
    for i in range(open_paren_index, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_index + 1 : i]
    return text[open_paren_index + 1 :]


# The Workflow runtime requires `meta` to be a PURE LITERAL — no variables, calls, spreads,
# string concatenation, or template interpolation. The node behavioral runner evaluates the
# script as plain JS (where `'a' + 'b'` is fine) so it CANNOT catch this; only the live
# runtime rejects it. This static check stands in for the runtime's meta validator so the
# whole class regresses in CI rather than at dispatch time.
_META_DECL_RE = re.compile(r"(?:export\s+)?const\s+meta\s*=\s*\{")
# A closing/opening quote adjacent to `+` is string concatenation (BinaryExpression);
# a `+` buried inside string content (e.g. "a+b") has non-quote neighbours and is ignored.
_META_CONCAT_RE = re.compile(r"""['"`]\s*\+|\+\s*['"`]""")


def _meta_block(text: str) -> str:
    m = _META_DECL_RE.search(text)
    assert m, "no `const meta = {` declaration found"
    start = m.end() - 1  # index of the opening brace
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError("unbalanced braces in meta literal")


def _orch_scripts() -> list[Path]:
    if not WORKFLOWS_DIR.is_dir():
        return []
    return sorted(p for p in WORKFLOWS_DIR.glob("*.orch.js") if not p.name.startswith("_"))


ORCH_SCRIPTS = _orch_scripts()
SCRIPT_IDS = [p.name for p in ORCH_SCRIPTS]


def test_at_least_one_orchestration_script() -> None:
    """Guard against the glob silently matching nothing (wrong path ⇒ vacuous suite)."""
    assert ORCH_SCRIPTS, f"no *.orch.js found under {WORKFLOWS_DIR}"


# ───────────────────────────── STATIC ─────────────────────────────


@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_args_prologue_present(script: Path) -> None:
    text = script.read_text(encoding="utf-8")
    assert ARGS_PROLOGUE in text, (
        f"{script.name}: missing required args prologue `{ARGS_PROLOGUE}` (#68969)"
    )


@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_no_scriptpath_or_name_workflow_arg(script: Path) -> None:
    text = script.read_text(encoding="utf-8")
    for call in _WORKFLOW_CALL_RE.finditer(text):
        region = _balanced_region(text, call.end() - 1)
        forbidden = _FORBIDDEN_KEY_RE.search(region)
        assert forbidden is None, (
            f"{script.name}: `{forbidden.group(1)}:` used as a Workflow() argument is "
            f"forbidden (scripts run inline via `script`)"
        )


@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_within_line_cap(script: Path) -> None:
    n = len(script.read_text(encoding="utf-8").splitlines())
    assert n <= MAX_ORCH_LINES, f"{script.name}: {n} lines exceeds cap {MAX_ORCH_LINES}"


@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_exports_meta(script: Path) -> None:
    text = script.read_text(encoding="utf-8")
    assert re.search(r"export\s+const\s+meta\b", text), (
        f"{script.name}: must `export const meta = {{...}}`"
    )


@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_meta_is_pure_literal(script: Path) -> None:
    """`meta` must be a pure literal — the live Workflow runtime rejects string
    concatenation / interpolation there, but the node stub runner does not catch it."""
    block = _meta_block(script.read_text(encoding="utf-8"))
    concat = _META_CONCAT_RE.search(block)
    assert concat is None, (
        f"{script.name}: `meta` uses string concatenation (`{concat.group(0).strip()}`) — "
        f"the Workflow runtime requires a pure literal; inline it into one string"
    )
    assert "${" not in block, (
        f"{script.name}: `meta` uses template interpolation (`${{`) — not a pure literal"
    )


# ─────────────────────── static-helper unit tests ───────────────────────
# The static checks above lean on two text-slicers; exercise their edge branches
# directly so a regression in the slicers can't quietly weaken every script check.


def test_balanced_region_handles_nested_and_unclosed() -> None:
    flat = "Workflow(a, b)tail"
    assert _balanced_region(flat, flat.index("(")) == "a, b"
    nested = "f((a, b), c)tail"
    assert _balanced_region(nested, nested.index("(")) == "(a, b), c"
    # unclosed paren: return the remainder rather than raising (the forbidden-key scan
    # still runs over whatever was opened).
    unclosed = "g(a, b"
    assert _balanced_region(unclosed, unclosed.index("(")) == "a, b"


def test_meta_block_extracts_only_the_literal() -> None:
    text = "const meta = { name: 'x', phases: [{ title: 'A' }] }\nconst A = 1"
    block = _meta_block(text)
    assert block.startswith("{") and block.endswith("}")
    assert "phases" in block and "const A" not in block


def test_meta_block_raises_on_unbalanced_braces() -> None:
    with pytest.raises(AssertionError):
        _meta_block("const meta = { name: 'x'")


# ───────────────────────────── BEHAVIORAL ─────────────────────────────


def _run(script: Path, mode: str) -> dict:
    """Invoke the node runner; parse the JSON report it prints on stdout."""
    proc = subprocess.run(
        [NODE, str(RUNNER), str(script), mode, str(BUNDLE)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"runner exited {proc.returncode} for {script.name} mode={mode}\n"
        f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
    )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise AssertionError(
            f"runner did not print JSON for {script.name} mode={mode}\n"
            f"stdout: {proc.stdout}\nstderr: {proc.stderr}"
        ) from exc


def _failed_ids(result: dict) -> set[str]:
    """Collect item ids the script marked failed — from `failed` list and/or ledger."""
    ids: set[str] = set()
    if not isinstance(result, dict):
        return ids
    for fid in result.get("failed", []) or []:
        ids.add(fid)
    for entry in result.get("ledger", []) or []:
        if isinstance(entry, dict) and entry.get("status") not in (None, "done"):
            ids.add(entry.get("id"))
    return ids


def _ledger_ids(result: dict) -> set[str]:
    ids: set[str] = set()
    for entry in (result or {}).get("ledger", []) or []:
        if isinstance(entry, dict) and "id" in entry:
            ids.add(entry["id"])
    return ids


@pytest.mark.skipif(NODE is None, reason="node not on PATH — behavioral run skipped")
@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_normal_run_completes(script: Path) -> None:
    report = _run(script, "normal")
    assert report["ok"] is True, f"{script.name}: normal run threw: {report.get('error')}"
    result = report.get("result")
    assert result is not None, f"{script.name}: normal run returned nothing"
    assert report.get("agentCalls", 0) > 0, f"{script.name}: normal run never spawned an agent"
    # The §6 ledger contract: every script returns a per-item `ledger` and a `failed` list,
    # not just some opaque blob. Asserting the shape catches a script that silently drops the
    # ledger (which would make the partial-failure guarantee unobservable to the main loop).
    assert isinstance(result, dict), f"{script.name}: result is not an object: {result!r}"
    assert "ledger" in result and "failed" in result, (
        f"{script.name}: result missing the ledger/failed envelope (keys={sorted(result)})"
    )
    # No item should be marked failed on a clean run.
    assert not _failed_ids(result), (
        f"{script.name}: clean run reported failures {_failed_ids(result)}"
    )


@pytest.mark.skipif(NODE is None, reason="node not on PATH — behavioral run skipped")
@pytest.mark.parametrize("mode", ["throw", "null", "invalid"])
@pytest.mark.parametrize("script", ORCH_SCRIPTS, ids=SCRIPT_IDS)
def test_fault_run_records_failure_not_drop(script: Path, mode: str) -> None:
    """A throwing / null / schema-invalid agent for one item must be journaled as failed,
    never silently dropped, and must not crash the run."""
    report = _run(script, mode)
    assert report["ok"] is True, (
        f"{script.name} mode={mode}: run crashed instead of journaling the failure: "
        f"{report.get('error')}"
    )
    result = report.get("result")
    assert result is not None, f"{script.name} mode={mode}: returned nothing"

    failed = _failed_ids(result)
    assert failed, (
        f"{script.name} mode={mode}: faulted item was silently dropped — "
        f"nothing recorded as failed (result={result})"
    )
    # The faulted item is the first item the runner dispatches: 'correctness'.
    assert "correctness" in failed, (
        f"{script.name} mode={mode}: expected 'correctness' among failed, got {failed}"
    )
    # Not silently dropped: the faulted item still appears in the ledger.
    ledger_ids = _ledger_ids(result)
    if ledger_ids:
        assert "correctness" in ledger_ids, (
            f"{script.name} mode={mode}: faulted item missing from ledger {ledger_ids}"
        )
