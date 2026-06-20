import hashlib
from pathlib import Path

import pytest

from cartograph.planning import state as st

PLAN = """---
title: T
type: feat
status: active
date: 2026-06-18
units:
  - id: 1
    title: U
    state: pending
---
# T — Plan
### Unit 1 — U
**State:** pending
"""


def _write(p: Path) -> Path:
    p.write_text(PLAN)
    return p


def test_atomic_write_uses_replace(tmp_path: Path):
    p = _write(tmp_path / "plan.md")
    plan = st.parse_plan(p)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    st.set_unit_state(plan, 1, "complete", commit="abc1234")
    st.write_plan_atomic(p, plan, expected_hash=h)
    assert st.parse_plan(p).units[0].state == "complete"


def test_optimistic_guard_aborts_on_concurrent_change(tmp_path: Path):
    p = _write(tmp_path / "plan.md")
    plan = st.parse_plan(p)
    stale = hashlib.sha256(b"different").hexdigest()
    st.set_unit_state(plan, 1, "complete", commit="abc1234")
    with pytest.raises(st.PlanConflictError):
        st.write_plan_atomic(p, plan, expected_hash=stale)
