from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import plan_status

FIXTURES = Path(__file__).parent / "fixtures" / "plans"


@pytest.fixture
def temp_plans_dir(tmp_path: Path) -> Path:
    target = tmp_path / "plans"
    target.mkdir()
    for name in ("legacy_minimal.md", "new_format.md", "superseded.md"):
        shutil.copy(FIXTURES / name, target / name)
    return target


class TestReport:
    def test_table_format_lists_every_plan(
        self, temp_plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = plan_status.main(["--plans-dir", str(temp_plans_dir), "report"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "legacy_minimal.md" in out
        assert "new_format.md" in out
        assert "superseded.md" in out

    def test_json_format_is_valid(
        self, temp_plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = plan_status.main(["--plans-dir", str(temp_plans_dir), "report", "--format", "json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert "plans" in payload
        files = {entry["path"].rsplit("/", 1)[-1] for entry in payload["plans"]}
        assert files >= {"legacy_minimal.md", "new_format.md", "superseded.md"}


class TestAudit:
    def test_audit_passes_on_clean_fixtures(self, temp_plans_dir: Path) -> None:
        rc = plan_status.main(["--plans-dir", str(temp_plans_dir), "audit"])
        assert rc == 0

    def test_audit_fails_on_complete_without_implemented_in(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        bad = plans_dir / "bad.md"
        bad.write_text(
            (
                "---\n"
                "title: Bad\n"
                "type: feat\n"
                "status: complete\n"
                "date: 2026-04-29\n"
                "units:\n"
                "  - id: 1\n"
                "    title: x\n"
                "    state: complete\n"
                "---\n\n"
                "## Implementation Units\n\n"
                "### Unit 1 — x\n\n"
                "**State:** complete\n\n"
                "- [x] Goal: x\n"
            ),
            encoding="utf-8",
        )
        rc = plan_status.main(["--plans-dir", str(plans_dir), "audit"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "implemented_in" in captured.err


class TestSetUnit:
    def test_set_unit_marks_state_and_commit(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "new_format.md"
        rc = plan_status.main(
            [
                "set-unit",
                str(plan_path),
                "3",
                "in_progress",
            ]
        )
        assert rc == 0
        from scripts.plan_state import parse_plan

        plan = parse_plan(plan_path)
        unit_3 = next(u for u in plan.units if u.id == 3)
        assert unit_3.state == "in_progress"

    def test_set_unit_complete_with_commit(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "new_format.md"
        rc = plan_status.main(
            [
                "set-unit",
                str(plan_path),
                "2",
                "complete",
                "--commit",
                "feedface",
            ]
        )
        assert rc == 0
        from scripts.plan_state import parse_plan

        plan = parse_plan(plan_path)
        unit_2 = next(u for u in plan.units if u.id == 2)
        assert unit_2.state == "complete"
        assert unit_2.implemented_in == "feedface"

    def test_set_unit_idempotent(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "new_format.md"
        argv = ["set-unit", str(plan_path), "3", "in_progress"]
        plan_status.main(argv)
        first = plan_path.read_text(encoding="utf-8")
        plan_status.main(argv)
        second = plan_path.read_text(encoding="utf-8")
        assert first == second


class TestSetStatus:
    def test_set_status_complete_records_commit(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "new_format.md"
        rc = plan_status.main(
            [
                "set-status",
                str(plan_path),
                "complete",
                "--implemented-in",
                "abc1234",
            ]
        )
        assert rc == 0
        from scripts.plan_state import parse_plan

        plan = parse_plan(plan_path)
        assert plan.status == "complete"
        assert plan.implemented_in == "abc1234"

    def test_set_status_complete_without_commit_fails(
        self, temp_plans_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        plan_path = temp_plans_dir / "legacy_minimal.md"
        rc = plan_status.main(["set-status", str(plan_path), "complete"])
        assert rc == 1
        assert "implemented_in" in capsys.readouterr().err

    def test_set_status_superseded(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "legacy_minimal.md"
        rc = plan_status.main(
            [
                "set-status",
                str(plan_path),
                "superseded",
                "--superseded-by",
                "docs/plans/replacement.md",
            ]
        )
        assert rc == 0
        from scripts.plan_state import parse_plan

        plan = parse_plan(plan_path)
        assert plan.status == "superseded"
        assert plan.superseded_by == "docs/plans/replacement.md"


class TestPlanResolution:
    def test_resolves_relative_path(self, temp_plans_dir: Path) -> None:
        plan_path = temp_plans_dir / "new_format.md"
        rc = plan_status.main(["set-unit", str(plan_path), "3", "in_progress"])
        assert rc == 0

    def test_unknown_plan_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            plan_status.main(["set-unit", str(tmp_path / "missing.md"), "1", "complete"])

    def test_set_unit_resolves_via_plans_dir_override(
        self, temp_plans_dir: Path
    ) -> None:
        rc = plan_status.main(
            [
                "--plans-dir",
                str(temp_plans_dir),
                "set-unit",
                "new_format.md",
                "3",
                "in_progress",
            ]
        )
        assert rc == 0

        from scripts.plan_state import parse_plan

        plan = parse_plan(temp_plans_dir / "new_format.md")
        unit_3 = next(u for u in plan.units if u.id == 3)
        assert unit_3.state == "in_progress"

    def test_set_status_resolves_via_plans_dir_override(
        self, temp_plans_dir: Path
    ) -> None:
        rc = plan_status.main(
            [
                "--plans-dir",
                str(temp_plans_dir),
                "set-status",
                "legacy_minimal.md",
                "abandoned",
                "--abandoned-reason",
                "test",
            ]
        )
        assert rc == 0

        from scripts.plan_state import parse_plan

        plan = parse_plan(temp_plans_dir / "legacy_minimal.md")
        assert plan.status == "abandoned"


class TestBranchMatch:
    def test_stopwords_alone_do_not_match(self, tmp_path: Path) -> None:
        from scripts.plan_state import Plan
        from scripts.plan_status import _branch_match

        plan = Plan(
            path=tmp_path / "2026-01-01-001-feat-something-plan.md",
            title="x",
            type="feat",
            status="active",
            date="2026-01-01",
        )
        # Branch shares only the generic "feat" stop-word; should NOT match.
        assert _branch_match("feat/unrelated", plan) is False
        # Branch shares the distinctive "something" part; should match.
        assert _branch_match("feat/something-bug", plan) is True

    def test_pure_stopword_slug_never_matches(self, tmp_path: Path) -> None:
        from scripts.plan_state import Plan
        from scripts.plan_status import _branch_match

        plan = Plan(
            path=tmp_path / "2026-01-01-001-feat-plan.md",
            title="x",
            type="feat",
            status="active",
            date="2026-01-01",
        )
        # All non-numeric parts are stop-words → no match possible.
        assert _branch_match("feat/anything", plan) is False
