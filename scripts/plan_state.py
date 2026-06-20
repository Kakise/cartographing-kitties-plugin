"""Thin shim — the plan-state library now ships in the package.

The implementation moved into the distributable package at
:mod:`cartograph.planning.state`. This shim re-exports the public names so
repo-local importers (and existing tests) continue to resolve
``from scripts.plan_state import ...``.
"""

from __future__ import annotations

from cartograph.planning.state import (  # noqa: F401
    PLAN_STATUSES,
    UNIT_STATES,
    Plan,
    PlanConflictError,
    PlanStatus,
    Unit,
    UnitState,
    ValidationError,
    compute_rollup,
    parse_plan,
    serialize_plan,
    set_plan_status,
    set_unit_state,
    validate,
    write_plan_atomic,
)

__all__ = [
    "PLAN_STATUSES",
    "UNIT_STATES",
    "Plan",
    "PlanConflictError",
    "PlanStatus",
    "Unit",
    "UnitState",
    "ValidationError",
    "compute_rollup",
    "parse_plan",
    "serialize_plan",
    "set_plan_status",
    "set_unit_state",
    "validate",
    "write_plan_atomic",
]
