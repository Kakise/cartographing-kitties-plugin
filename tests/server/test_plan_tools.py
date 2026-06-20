"""Unit tests for the plan MCP tools (``cartograph.server.tools.plan``).

The ``@mcp.tool()`` decorator returns the underlying function unchanged, so the
tools are called directly here (the same convention used by
``tests/test_tool_contracts.py`` and ``tests/test_server.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cartograph.planning.state import parse_plan
from cartograph.server.tools.plan import (
    plan_audit,
    plan_create,
    plan_set_status,
    plan_set_unit_state,
    plan_status,
)

PLAN = """---
title: T
type: feat
status: active
date: 2026-06-18
units:
  - id: 1
    title: U1
    state: pending
  - id: 2
    title: U2
    state: pending
---
# T — Plan

### Unit 1 — U1

**State:** pending

### Unit 2 — U2

**State:** pending
"""


@pytest.fixture
def plan_path(tmp_path: Path) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(PLAN, encoding="utf-8")
    return p


def test_plan_status_returns_rollup_and_units(plan_path: Path) -> None:
    result = plan_status(str(plan_path))
    assert result["status"] == "active"
    units = result["units"]
    assert len(units) == 2
    first = units[0]
    assert first["id"] == 1
    assert first["title"] == "U1"
    assert first["state"] == "pending"
    assert first["implemented_in"] is None


def test_plan_set_unit_state_flips_unit_and_persists(plan_path: Path) -> None:
    result = plan_set_unit_state(str(plan_path), 1, "complete", "abc1234")
    assert result["ok"] is True

    # Re-read from disk via the library — the change must be persisted.
    reread = parse_plan(plan_path)
    unit_1 = next(u for u in reread.units if u.id == 1)
    assert unit_1.state == "complete"
    assert unit_1.implemented_in == "abc1234"

    # And the tool's own status view reflects it.
    status_view = plan_status(str(plan_path))
    unit_1_view = next(u for u in status_view["units"] if u["id"] == 1)
    assert unit_1_view["state"] == "complete"
    assert unit_1_view["implemented_in"] == "abc1234"


def test_plan_set_status_marks_plan_complete(plan_path: Path) -> None:
    result = plan_set_status(str(plan_path), "complete", implemented_in="deadbee")
    assert result["ok"] is True
    reread = parse_plan(plan_path)
    assert reread.status == "complete"
    assert reread.implemented_in == "deadbee"


def test_plan_audit_single_plan_ok(plan_path: Path) -> None:
    result = plan_audit(str(plan_path))
    assert result["ok"] is True
    assert result["errors"] == []


def test_plan_audit_reports_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text(
        (
            "---\n"
            "title: Bad\n"
            "type: feat\n"
            "status: complete\n"
            "date: 2026-06-18\n"
            "units:\n"
            "  - id: 1\n"
            "    title: x\n"
            "    state: complete\n"
            "---\n\n"
            "### Unit 1 — x\n\n"
            "**State:** complete\n"
        ),
        encoding="utf-8",
    )
    result = plan_audit(str(bad))
    assert result["ok"] is False
    assert any("implemented_in" in err for err in result["errors"])


def test_plan_create_writes_file_with_units(tmp_path: Path) -> None:
    target = tmp_path / "created.md"
    result = plan_create(
        str(target),
        "Created Plan",
        "feat",
        [{"id": 1, "title": "First"}, {"id": 2, "title": "Second"}],
    )
    assert result["ok"] is True
    assert target.exists()
    reread = parse_plan(target)
    assert reread.title == "Created Plan"
    assert [u.id for u in reread.units] == [1, 2]
    assert all(u.state == "pending" for u in reread.units)
