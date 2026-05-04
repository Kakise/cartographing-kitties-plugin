"""Tests for the JSONL telemetry writer."""

from __future__ import annotations

import gzip
import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cartograph.telemetry import (
    GZIP_AFTER_DAYS,
    LIVE_FILENAME,
    REQUIRED_FIELDS,
    append_record,
    build_record,
)


def _example_record(**overrides: object) -> dict[str, object]:
    base = build_record(
        skill="kitty:plan",
        duration_ms=1234,
        tool_calls=10,
        tokens_in=2048,
        tokens_out=512,
        agents_spawned=2,
        exit_status="ok",
        run_id="run-xyz",
        ts=int(time.time()),
    )
    base.update(overrides)
    return base


def test_build_record_carries_required_fields() -> None:
    record = _example_record()
    for key, expected_type in REQUIRED_FIELDS.items():
        assert key in record, f"missing {key!r}"
        assert isinstance(record[key], expected_type)


def test_append_record_writes_jsonl(tmp_path: Path) -> None:
    live = append_record(tmp_path, _example_record())
    assert live == tmp_path / LIVE_FILENAME

    lines = live.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    decoded = json.loads(lines[0])
    assert decoded["skill"] == "kitty:plan"
    assert decoded["run_id"] == "run-xyz"


def test_append_appends(tmp_path: Path) -> None:
    append_record(tmp_path, _example_record(run_id="r1"))
    append_record(tmp_path, _example_record(run_id="r2"))

    lines = (tmp_path / LIVE_FILENAME).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["run_id"] for line in lines] == ["r1", "r2"]


def test_append_validates_required_fields(tmp_path: Path) -> None:
    record = _example_record()
    record.pop("run_id")
    with pytest.raises(ValueError, match="run_id"):
        append_record(tmp_path, record)


def test_append_validates_field_types(tmp_path: Path) -> None:
    record = _example_record()
    record["duration_ms"] = "1234"  # wrong type
    with pytest.raises(ValueError, match="duration_ms"):
        append_record(tmp_path, record)


def test_rotation_renames_yesterdays_live_file(tmp_path: Path) -> None:
    live = tmp_path / LIVE_FILENAME
    live.write_text(json.dumps(_example_record(run_id="yesterday")) + "\n", encoding="utf-8")

    # Backdate the file so rotation kicks in.
    yesterday = datetime.now(tz=UTC) - timedelta(days=1)
    timestamp = yesterday.timestamp()
    os.utime(live, (timestamp, timestamp))

    append_record(tmp_path, _example_record(run_id="today"))

    rotated = tmp_path / f"telemetry.{yesterday.date().isoformat()}.jsonl"
    assert rotated.exists(), f"expected rotated file at {rotated}"
    assert "yesterday" in rotated.read_text(encoding="utf-8")

    today_lines = live.read_text(encoding="utf-8").splitlines()
    assert len(today_lines) == 1
    assert json.loads(today_lines[0])["run_id"] == "today"


def test_old_rotated_files_are_gzipped(tmp_path: Path) -> None:
    today = datetime.now(tz=UTC).date()
    old_day = today - timedelta(days=GZIP_AFTER_DAYS + 2)
    old_path = tmp_path / f"telemetry.{old_day.isoformat()}.jsonl"
    old_path.write_text("{}\n", encoding="utf-8")

    append_record(tmp_path, _example_record(run_id="trigger-rotation"))

    gz_path = old_path.with_suffix(".jsonl.gz")
    assert gz_path.exists(), "old rotated file should be gzipped"
    assert not old_path.exists(), "uncompressed rotated file should be removed"
    with gzip.open(gz_path, "rt", encoding="utf-8") as handle:
        assert handle.read() == "{}\n"
