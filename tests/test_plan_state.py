from __future__ import annotations

from pathlib import Path

import pytest

from scripts.plan_state import (
    Plan,
    Unit,
    compute_rollup,
    parse_plan,
    serialize_plan,
    set_plan_status,
    set_unit_state,
    validate,
)

FIXTURES = Path(__file__).parent / "fixtures" / "plans"


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


class TestParseLegacy:
    def test_legacy_plan_defaults_units_to_pending(self) -> None:
        plan = parse_plan(FIXTURES / "legacy_minimal.md")
        assert plan.status == "active"
        assert len(plan.units) == 2
        assert plan.units[0].id == 1
        assert plan.units[0].title == "First step"
        assert plan.units[0].state == "pending"
        assert plan.units[1].id == 2
        assert plan.units[1].title == "Second step"
        assert plan.units[1].state == "pending"

    def test_legacy_plan_has_no_implementation_pointers(self) -> None:
        plan = parse_plan(FIXTURES / "legacy_minimal.md")
        assert plan.implemented_in is None
        assert plan.superseded_by is None
        assert plan.abandoned_reason is None


class TestParseNewFormat:
    def test_new_format_extracts_unit_states(self) -> None:
        plan = parse_plan(FIXTURES / "new_format.md")
        states = [u.state for u in plan.units]
        assert states == ["complete", "in_progress", "pending"]
        assert plan.units[0].implemented_in == "abc1234"

    def test_new_format_round_trips_byte_equal(self) -> None:
        path = FIXTURES / "new_format.md"
        plan = parse_plan(path)
        original = path.read_text(encoding="utf-8")
        assert serialize_plan(plan) == original


class TestParseSuperseded:
    def test_superseded_plan_carries_pointer(self) -> None:
        plan = parse_plan(FIXTURES / "superseded.md")
        assert plan.status == "superseded"
        assert plan.superseded_by == ("docs/plans/2026-01-01-001-feat-replacement-plan.md")
        assert plan.units[0].state == "skipped"
        assert plan.units[0].skipped_reason == "Replaced by alternative design"


class TestRollup:
    @pytest.mark.parametrize(
        "states,expected",
        [
            (["pending", "pending"], "active"),
            (["complete", "pending"], "in_progress"),
            (["in_progress", "pending"], "in_progress"),
            (["complete", "complete"], "complete"),
            (["complete", "skipped"], "complete"),
            (["skipped", "skipped"], "complete"),
            ([], "active"),
        ],
    )
    def test_rollup_table(self, states: list[str], expected: str) -> None:
        units = [Unit(id=i + 1, title=f"u{i}", state=s) for i, s in enumerate(states)]  # type: ignore[arg-type]
        assert compute_rollup(units) == expected


class TestValidate:
    def test_complete_requires_implemented_in(self, tmp_path: Path) -> None:
        plan = Plan(
            path=tmp_path / "p.md",
            title="x",
            type="feat",
            status="complete",
            date="2026-04-29",
            units=[Unit(id=1, title="x", state="complete")],
        )
        errors = validate(plan)
        assert any("implemented_in" in str(e) for e in errors)

    def test_superseded_requires_pointer(self, tmp_path: Path) -> None:
        plan = Plan(
            path=tmp_path / "p.md",
            title="x",
            type="feat",
            status="superseded",
            date="2026-04-29",
        )
        errors = validate(plan)
        assert any("superseded_by" in str(e) for e in errors)

    def test_abandoned_requires_reason(self, tmp_path: Path) -> None:
        plan = Plan(
            path=tmp_path / "p.md",
            title="x",
            type="feat",
            status="abandoned",
            date="2026-04-29",
        )
        errors = validate(plan)
        assert any("abandoned_reason" in str(e) for e in errors)

    def test_status_disagrees_with_rollup_is_error(self, tmp_path: Path) -> None:
        plan = Plan(
            path=tmp_path / "p.md",
            title="x",
            type="feat",
            status="active",
            date="2026-04-29",
            units=[
                Unit(id=1, title="x", state="complete", implemented_in="ab"),
                Unit(id=2, title="y", state="pending"),
            ],
        )
        errors = validate(plan)
        assert any("disagrees with rollup" in str(e) for e in errors)

    def test_skipped_unit_requires_reason(self, tmp_path: Path) -> None:
        plan = Plan(
            path=tmp_path / "p.md",
            title="x",
            type="feat",
            status="active",
            date="2026-04-29",
            units=[Unit(id=1, title="x", state="skipped")],
        )
        errors = validate(plan)
        assert any("skipped" in str(e) for e in errors)

    def test_valid_new_format_passes(self) -> None:
        plan = parse_plan(FIXTURES / "new_format.md")
        assert validate(plan) == []


class TestSetUnitState:
    def test_set_unit_state_updates_rollup(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        assert plan.status == "in_progress"
        set_unit_state(plan, 2, "complete", implemented_in="def5678")
        # Units 1+2 complete, 3 pending → rollup stays in_progress.
        assert plan.status == "in_progress"
        assert plan.units[1].implemented_in == "def5678"

        set_unit_state(plan, 3, "complete", implemented_in="def5678")
        # All complete → rollup propagates to plan.status.
        assert plan.status == "complete"

    def test_set_unit_state_round_trips(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        set_unit_state(plan, 2, "complete", implemented_in="deadbeef")
        path.write_text(serialize_plan(plan), encoding="utf-8")
        reparsed = parse_plan(path)
        unit_2 = next(u for u in reparsed.units if u.id == 2)
        assert unit_2.state == "complete"
        assert unit_2.implemented_in == "deadbeef"

    def test_set_unit_state_unknown_id_raises(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        with pytest.raises(ValueError, match="unit 99"):
            set_unit_state(plan, 99, "complete")

    def test_idempotent_set_state(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        set_unit_state(plan, 2, "in_progress")
        first = serialize_plan(plan)
        set_unit_state(plan, 2, "in_progress")
        second = serialize_plan(plan)
        assert first == second


class TestSetPlanStatus:
    def test_complete_promotes_units_and_records_implemented_in(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        set_plan_status(plan, "complete", implemented_in="cafebabe")
        assert plan.status == "complete"
        assert plan.implemented_in == "cafebabe"
        for unit in plan.units:
            assert unit.state == "complete"

    def test_superseded_clears_implemented_in(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        set_plan_status(plan, "complete", implemented_in="cafebabe")
        set_plan_status(
            plan,
            "superseded",
            superseded_by="docs/plans/replacement.md",
        )
        assert plan.implemented_in is None
        assert plan.superseded_by == "docs/plans/replacement.md"

    def test_abandoned_records_reason(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            "p.md",
            (FIXTURES / "new_format.md").read_text(encoding="utf-8"),
        )
        plan = parse_plan(path)
        set_plan_status(plan, "abandoned", abandoned_reason="No longer needed")
        assert plan.status == "abandoned"
        assert plan.abandoned_reason == "No longer needed"


class TestFencedBlockIsolation:
    def test_fenced_examples_do_not_contaminate_units(self) -> None:
        plan = parse_plan(FIXTURES / "with_fenced_examples.md")
        assert len(plan.units) == 1
        unit = plan.units[0]
        assert unit.title == "Real first unit"
        assert unit.state == "pending"
        assert unit.implemented_in is None

    def test_serialize_does_not_inject_state_into_fenced_examples(self, tmp_path: Path) -> None:
        original = (FIXTURES / "with_fenced_examples.md").read_text(encoding="utf-8")
        path = _write(tmp_path, "p.md", original)
        plan = parse_plan(path)
        rewritten = serialize_plan(plan)
        # The fenced example's "**State:**" line must remain intact at "complete — implemented in deadbeef".
        assert "**State:** complete — implemented in deadbeef" in rewritten
        # The real Unit 1 keeps its pending state line.
        assert "**State:** pending" in rewritten


class TestSerializeRoundTrip:
    def test_legacy_plan_gains_units_block_after_serialize(self, tmp_path: Path) -> None:
        legacy = (FIXTURES / "legacy_minimal.md").read_text(encoding="utf-8")
        path = _write(tmp_path, "p.md", legacy)
        plan = parse_plan(path)
        rewritten = serialize_plan(plan)
        assert "units:" in rewritten
        assert "**State:** pending" in rewritten

        path.write_text(rewritten, encoding="utf-8")
        reparsed = parse_plan(path)
        assert [u.id for u in reparsed.units] == [1, 2]
        assert all(u.state == "pending" for u in reparsed.units)
