"""Append-only JSONL telemetry writer for skill runs.

Each skill run emits a single line to ``.pawprints/telemetry.jsonl`` capturing
duration, tool/agent counts, approximate token usage, and exit status. Files
are rotated daily — the live file is always ``telemetry.jsonl``; on the first
write of a new UTC day the previous file is renamed to
``telemetry.YYYY-MM-DD.jsonl``. Files older than ``GZIP_AFTER_DAYS`` are
gzipped in place during rotation.

The schema is intentionally narrow: callers append a fully-built dict, and the
writer only validates required keys + types. No background threads, no
filesystem watches — rotation happens lazily on each call.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

LIVE_FILENAME = "telemetry.jsonl"
ROTATED_PREFIX = "telemetry."
GZIP_AFTER_DAYS = 7

REQUIRED_FIELDS: dict[str, type] = {
    "ts": int,
    "skill": str,
    "duration_ms": int,
    "tool_calls": int,
    "tokens_in": int,
    "tokens_out": int,
    "agents_spawned": int,
    "exit_status": str,
    "run_id": str,
}


def _today_utc() -> date:
    return datetime.now(tz=UTC).date()


def _rotated_name(day: date) -> str:
    return f"{ROTATED_PREFIX}{day.isoformat()}.jsonl"


def _gzip_old_files(directory: Path, *, today: date, max_age_days: int) -> None:
    """Gzip rotated files older than ``max_age_days``."""

    threshold = today.toordinal() - max_age_days
    for path in directory.glob(f"{ROTATED_PREFIX}*.jsonl"):
        try:
            stem = path.stem.replace(ROTATED_PREFIX, "", 1)
            file_day = date.fromisoformat(stem)
        except ValueError:
            continue
        if file_day.toordinal() >= threshold:
            continue
        gz_path = path.with_suffix(".jsonl.gz")
        if gz_path.exists():
            continue
        with path.open("rb") as src, gzip.open(gz_path, "wb") as dst:
            dst.writelines(src)
        path.unlink()


def _rotate_if_stale(live_path: Path, *, today: date) -> None:
    """If ``live_path`` was last written before ``today``, rotate it."""

    if not live_path.exists() or live_path.stat().st_size == 0:
        return
    mtime = datetime.fromtimestamp(live_path.stat().st_mtime, tz=UTC).date()
    if mtime >= today:
        return
    rotated = live_path.with_name(_rotated_name(mtime))
    if rotated.exists():
        # Append rather than clobber.
        with live_path.open("rb") as src, rotated.open("ab") as dst:
            dst.writelines(src)
        live_path.unlink()
    else:
        live_path.rename(rotated)


def _validate_record(record: dict[str, Any]) -> None:
    for key, expected_type in REQUIRED_FIELDS.items():
        if key not in record:
            raise ValueError(f"telemetry record missing required key: {key!r}")
        if not isinstance(record[key], expected_type):
            raise ValueError(
                f"telemetry field {key!r} must be {expected_type.__name__}, "
                f"got {type(record[key]).__name__}"
            )


def append_record(directory: Path | str, record: dict[str, Any]) -> Path:
    """Append a telemetry record to ``directory/telemetry.jsonl``.

    Performs daily rotation (renaming the previous live file) and gzips files
    older than :data:`GZIP_AFTER_DAYS` lazily. Returns the live file path so
    callers can observe rotation easily.
    """

    _validate_record(record)
    directory_path = Path(directory)
    directory_path.mkdir(parents=True, exist_ok=True)
    live_path = directory_path / LIVE_FILENAME

    today = _today_utc()
    _rotate_if_stale(live_path, today=today)
    _gzip_old_files(directory_path, today=today, max_age_days=GZIP_AFTER_DAYS)

    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with live_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    # Touch mtime so subsequent rotation logic sees today's write.
    os.utime(live_path, (time.time(), time.time()))
    return live_path


def build_record(
    *,
    skill: str,
    duration_ms: int,
    tool_calls: int,
    tokens_in: int,
    tokens_out: int,
    agents_spawned: int,
    exit_status: str,
    run_id: str,
    ts: int | None = None,
) -> dict[str, Any]:
    """Assemble a telemetry record dict with the canonical field set."""

    return {
        "ts": ts if ts is not None else int(time.time()),
        "skill": skill,
        "duration_ms": duration_ms,
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "agents_spawned": agents_spawned,
        "exit_status": exit_status,
        "run_id": run_id,
    }
