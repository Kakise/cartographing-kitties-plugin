"""Plan-state library: parse, serialize, validate, and safely mutate plan docs.

Public surface re-exported from :mod:`cartograph.planning.state` so callers can
``from cartograph.planning import parse_plan`` without reaching into submodules.
"""

from __future__ import annotations

from cartograph.planning.state import (
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
