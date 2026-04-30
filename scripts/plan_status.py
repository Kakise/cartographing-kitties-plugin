"""CLI for inspecting and mutating plan documents under ``docs/plans/``.

Subcommands:
    report     Render a status dashboard across all plans (default).
    audit      Validate every plan; exit non-zero on errors.
    set-unit   Mutate one unit's state in a plan file.
    set-status Mutate the plan-level status in a plan file.

Built on ``scripts.plan_state``; the parser is the single source of truth
for plan format and mutation semantics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.plan_state import (  # noqa: E402
    PLAN_STATUSES,
    UNIT_STATES,
    Plan,
    parse_plan,
    serialize_plan,
    set_plan_status,
    set_unit_state,
    validate,
)


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLANS_DIR = REPO_ROOT / "docs" / "plans"


def _iter_plans(plans_dir: Path) -> list[Plan]:
    plans: list[Plan] = []
    for path in sorted(plans_dir.glob("*.md")):
        plans.append(parse_plan(path))
    return plans


def _git_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    branch = result.stdout.strip()
    return branch or None


def _git_log_for_path(path: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--", str(path.relative_to(REPO_ROOT))],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, ValueError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _branch_match(branch: str | None, plan: Plan) -> bool:
    if not branch:
        return False
    slug = plan.path.stem
    parts = [part for part in slug.split("-") if not part.isdigit() and len(part) > 2]
    return any(part in branch for part in parts)


def _unit_tally(plan: Plan) -> dict[str, int]:
    tally = {state: 0 for state in UNIT_STATES}
    for unit in plan.units:
        tally[unit.state] += 1
    return tally


def _plan_to_dict(plan: Plan, *, branch: str | None) -> dict[str, Any]:
    tally = _unit_tally(plan)
    try:
        rel_path = str(plan.path.relative_to(REPO_ROOT))
    except ValueError:
        rel_path = str(plan.path)
    return {
        "path": rel_path,
        "title": plan.title,
        "type": plan.type,
        "status": plan.status,
        "implemented_in": plan.implemented_in,
        "superseded_by": plan.superseded_by,
        "abandoned_reason": plan.abandoned_reason,
        "units_total": len(plan.units),
        "units": tally,
        "branch_match": _branch_match(branch, plan),
    }


def _render_table(plans: list[Plan], branch: str | None) -> str:
    rows: list[list[str]] = [
        ["File", "Status", "Units", "Type", "Notes"],
    ]
    for plan in plans:
        tally = _unit_tally(plan)
        units_label = (
            f"{tally['complete']}/{len(plan.units)} complete" if plan.units else "no units"
        )
        notes_parts: list[str] = []
        if plan.implemented_in:
            notes_parts.append(f"impl={plan.implemented_in}")
        if plan.superseded_by:
            notes_parts.append(f"by={plan.superseded_by}")
        if plan.abandoned_reason:
            notes_parts.append(f"reason={plan.abandoned_reason}")
        if _branch_match(branch, plan):
            notes_parts.append("branch-match")
        rows.append(
            [
                plan.path.name,
                plan.status,
                units_label,
                plan.type,
                "; ".join(notes_parts),
            ]
        )

    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    out: list[str] = []
    for row_idx, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
        out.append(line)
        if row_idx == 0:
            out.append("  ".join("-" * widths[i] for i in range(len(widths))))
    return "\n".join(out) + "\n"


def cmd_report(args: argparse.Namespace) -> int:
    plans_dir = Path(args.plans_dir) if args.plans_dir else PLANS_DIR
    plans = _iter_plans(plans_dir)
    branch = _git_branch()
    if args.format == "json":
        payload = {
            "branch": branch,
            "plans": [_plan_to_dict(plan, branch=branch) for plan in plans],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(_render_table(plans, branch))
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    plans_dir = Path(args.plans_dir) if args.plans_dir else PLANS_DIR
    errors: list[str] = []
    for plan in _iter_plans(plans_dir):
        for err in validate(plan):
            errors.append(str(err))
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    return 0


def _resolve_plan(arg: str) -> Path:
    candidate = Path(arg)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    rel = REPO_ROOT / arg
    if rel.exists():
        return rel
    name = PLANS_DIR / arg
    if name.exists():
        return name
    raise FileNotFoundError(f"plan not found: {arg}")


def cmd_set_unit(args: argparse.Namespace) -> int:
    path = _resolve_plan(args.plan)
    plan = parse_plan(path)
    if args.state not in UNIT_STATES:
        print(f"invalid state: {args.state}", file=sys.stderr)
        return 2
    set_unit_state(
        plan,
        args.unit_id,
        args.state,
        implemented_in=args.commit,
        skipped_reason=args.reason,
    )
    errors = validate(plan)
    if errors:
        for err in errors:
            print(str(err), file=sys.stderr)
        return 1
    path.write_text(serialize_plan(plan), encoding="utf-8")
    return 0


def cmd_set_status(args: argparse.Namespace) -> int:
    path = _resolve_plan(args.plan)
    plan = parse_plan(path)
    if args.status not in PLAN_STATUSES:
        print(f"invalid status: {args.status}", file=sys.stderr)
        return 2
    set_plan_status(
        plan,
        args.status,
        implemented_in=args.implemented_in,
        superseded_by=args.superseded_by,
        abandoned_reason=args.abandoned_reason,
    )
    errors = validate(plan)
    if errors:
        for err in errors:
            print(str(err), file=sys.stderr)
        return 1
    path.write_text(serialize_plan(plan), encoding="utf-8")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plans-dir",
        default=None,
        help="Override docs/plans/ location (default: <repo>/docs/plans).",
    )
    sub = parser.add_subparsers(dest="command")

    report = sub.add_parser("report", help="Render plan status dashboard.")
    report.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format (default: table).",
    )
    report.set_defaults(func=cmd_report)

    audit = sub.add_parser("audit", help="Validate every plan.")
    audit.add_argument(
        "--strict",
        action="store_true",
        help="Reserved; today audit is already strict about every validation rule.",
    )
    audit.set_defaults(func=cmd_audit)

    set_unit = sub.add_parser("set-unit", help="Mutate a unit's state.")
    set_unit.add_argument("plan", help="Plan file (relative or absolute).")
    set_unit.add_argument("unit_id", type=int, help="Unit id (integer).")
    set_unit.add_argument(
        "state",
        choices=UNIT_STATES,
        help="New unit state.",
    )
    set_unit.add_argument(
        "--commit",
        default=None,
        help="Commit hash to record in unit's implemented_in (used when state=complete).",
    )
    set_unit.add_argument(
        "--reason",
        default=None,
        help="Skipped reason (used when state=skipped).",
    )
    set_unit.set_defaults(func=cmd_set_unit)

    set_status = sub.add_parser("set-status", help="Mutate plan-level status.")
    set_status.add_argument("plan", help="Plan file (relative or absolute).")
    set_status.add_argument(
        "status",
        choices=PLAN_STATUSES,
        help="New plan status.",
    )
    set_status.add_argument(
        "--implemented-in",
        default=None,
        help="Commit hash (used when status=complete).",
    )
    set_status.add_argument(
        "--superseded-by",
        default=None,
        help="Path to replacement plan (used when status=superseded).",
    )
    set_status.add_argument(
        "--abandoned-reason",
        default=None,
        help="One-line reason (used when status=abandoned).",
    )
    set_status.set_defaults(func=cmd_set_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # Default to `report` when no subcommand is given.
        args.format = "table"
        return cmd_report(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
