"""Plan-state MCP tools.

Thin ``@mcp.tool()`` wrappers over :mod:`cartograph.planning.state`. They let
an agent inspect and mutate plan documents under ``docs/plans/`` without
shelling out to the CLI. Mutating tools follow the read-hash -> parse ->
mutate -> :func:`write_plan_atomic` pattern so a concurrent edit aborts with a
:class:`PlanConflictError` instead of clobbering the file.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from cartograph.planning.state import (
    Plan,
    PlanConflictError,
    Unit,
    compute_rollup,
    parse_plan,
    set_plan_status,
    set_unit_state,
    validate,
    write_plan_atomic,
)
from cartograph.server.main import mcp


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _units_payload(plan: Plan) -> list[dict[str, Any]]:
    return [
        {
            "id": unit.id,
            "title": unit.title,
            "state": unit.state,
            "implemented_in": unit.implemented_in,
        }
        for unit in plan.units
    ]


def _conflict(exc: PlanConflictError) -> dict[str, Any]:
    return {"ok": False, "error": "conflict", "message": str(exc)}


def _validation_failure(errors: list[str]) -> dict[str, Any]:
    return {"ok": False, "error": "validation", "errors": errors}


@mcp.tool()
def plan_create(path: str, title: str, type: str, units: list[dict]) -> dict:
    """Create a new plan document at *path* with *title*, *type*, and *units*.

    ``units`` is a list of dicts; each needs at least an ``id`` and ``title``
    and may set ``state`` (defaults to ``pending``). Refuses to overwrite an
    existing file. Returns ``{"ok": True, "path": ..., "units": [...]}``.
    """
    target = Path(path)
    if target.exists():
        return {"ok": False, "error": "exists", "message": f"{target} already exists"}

    parsed_units: list[Unit] = []
    for entry in units:
        if "id" not in entry:
            return {"ok": False, "error": "bad_unit", "message": "each unit needs an 'id'"}
        parsed_units.append(
            Unit(
                id=int(entry["id"]),
                title=str(entry.get("title", "")),
                state=entry.get("state", "pending"),
                implemented_in=entry.get("implemented_in"),
                skipped_reason=entry.get("skipped_reason"),
            )
        )

    body_lines = [f"# {title}", ""]
    for unit in parsed_units:
        body_lines.append(f"### Unit {unit.id} — {unit.title}")
        body_lines.append("")
        body_lines.append(f"**State:** {unit.state}")
        body_lines.append("")
    body = "\n".join(body_lines)

    plan = Plan(
        path=target,
        title=title,
        type=type,
        status="active",
        date="",
        units=parsed_units,
        body=body,
    )
    if plan.units:
        plan.status = compute_rollup(plan.units)

    errors = [str(err) for err in validate(plan)]
    if errors:
        return _validation_failure(errors)

    target.parent.mkdir(parents=True, exist_ok=True)
    # No expected_hash: the file does not exist yet (and we already refused to
    # overwrite an existing one above).
    write_plan_atomic(target, plan, expected_hash=None)
    return {"ok": True, "path": str(target), "status": plan.status, "units": _units_payload(plan)}


@mcp.tool()
def plan_status(path: str) -> dict:
    """Return the rollup status and per-unit states for the plan at *path*.

    Shape: ``{"status": <rollup>, "units": [{"id", "title", "state",
    "implemented_in"}, ...]}``.
    """
    plan = parse_plan(Path(path))
    return {"status": plan.status, "units": _units_payload(plan)}


@mcp.tool()
def plan_set_unit_state(
    path: str,
    unit_id: int,
    state: str,
    commit: str | None = None,
    reason: str | None = None,
) -> dict:
    """Set *unit_id*'s ``state`` in the plan at *path* (atomic, conflict-guarded).

    ``commit`` records ``implemented_in`` (for ``state=complete``); ``reason``
    records the skipped reason (for ``state=skipped``). Returns ``{"ok": True,
    "status": <rollup>, "units": [...]}`` or an error dict on validation
    failure / concurrent change.
    """
    target = Path(path)
    expected_hash = _file_hash(target)
    plan = parse_plan(target)
    set_unit_state(plan, unit_id, state, implemented_in=commit, skipped_reason=reason)  # type: ignore[arg-type]
    errors = [str(err) for err in validate(plan)]
    if errors:
        return _validation_failure(errors)
    try:
        write_plan_atomic(target, plan, expected_hash=expected_hash)
    except PlanConflictError as exc:
        return _conflict(exc)
    return {"ok": True, "status": plan.status, "units": _units_payload(plan)}


@mcp.tool()
def plan_set_status(
    path: str,
    status: str,
    implemented_in: str | None = None,
    superseded_by: str | None = None,
    abandoned_reason: str | None = None,
) -> dict:
    """Set the plan-level ``status`` for the plan at *path* (atomic, guarded).

    Pass ``implemented_in`` for ``status=complete``, ``superseded_by`` for
    ``status=superseded``, or ``abandoned_reason`` for ``status=abandoned``.
    Returns ``{"ok": True, "status": ..., "units": [...]}`` or an error dict.
    """
    target = Path(path)
    expected_hash = _file_hash(target)
    plan = parse_plan(target)
    set_plan_status(
        plan,
        status,  # type: ignore[arg-type]
        implemented_in=implemented_in,
        superseded_by=superseded_by,
        abandoned_reason=abandoned_reason,
    )
    errors = [str(err) for err in validate(plan)]
    if errors:
        return _validation_failure(errors)
    try:
        write_plan_atomic(target, plan, expected_hash=expected_hash)
    except PlanConflictError as exc:
        return _conflict(exc)
    return {"ok": True, "status": plan.status, "units": _units_payload(plan)}


@mcp.tool()
def plan_audit(path: str | None = None) -> dict:
    """Validate one plan (when *path* is given) or every plan under ``docs/plans/``.

    Returns ``{"ok": bool, "errors": [...]}`` where each error is a rendered
    ``"<path>: <message>"`` string.
    """
    if path is not None:
        plan_paths = [Path(path)]
    else:
        plans_dir = Path.cwd() / "docs" / "plans"
        plan_paths = sorted(plans_dir.glob("*.md"))

    errors: list[str] = []
    for plan_path in plan_paths:
        plan = parse_plan(plan_path)
        errors.extend(str(err) for err in validate(plan))
    return {"ok": not errors, "errors": errors}
