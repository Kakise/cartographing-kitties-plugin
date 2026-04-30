"""Parse, serialize, and validate plan documents under ``docs/plans/``.

The module is intentionally side-effect free apart from file reads in
:func:`parse_plan`. The CLI lives in ``scripts/plan_status.py``.
"""

from __future__ import annotations

import datetime as _datetime
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

import yaml

PlanStatus = Literal[
    "draft",
    "active",
    "in_progress",
    "complete",
    "superseded",
    "abandoned",
]
UnitState = Literal["pending", "in_progress", "complete", "skipped"]

PLAN_STATUSES: tuple[PlanStatus, ...] = get_args(PlanStatus)
UNIT_STATES: tuple[UnitState, ...] = get_args(UnitState)


@dataclass
class Unit:
    id: int
    title: str
    state: UnitState = "pending"
    implemented_in: str | None = None
    skipped_reason: str | None = None


@dataclass
class Plan:
    path: Path
    title: str
    type: str
    status: PlanStatus
    date: str
    origin: str | None = None
    parent: str | None = None
    implemented_in: str | None = None
    superseded_by: str | None = None
    abandoned_reason: str | None = None
    verifies: list[str] = field(default_factory=list)
    aggregates: list[str] = field(default_factory=list)
    supersedes: str | None = None
    plans: list[str] = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    extra_frontmatter: dict[str, Any] = field(default_factory=dict)
    body: str = ""


@dataclass
class ValidationError:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


_KNOWN_FRONTMATTER_KEYS = {
    "title",
    "type",
    "status",
    "date",
    "origin",
    "parent",
    "implemented_in",
    "superseded_by",
    "abandoned_reason",
    "verifies",
    "aggregates",
    "supersedes",
    "plans",
    "units",
}

_UNIT_HEADER_RE = re.compile(
    r"^(?:###[ \t]+Unit[ \t]+|##[ \t]+U)(\d+)[ \t]*[—:\-][ \t]*(.+?)[ \t]*$",
    re.MULTILINE,
)
_STATE_LINE_RE = re.compile(r"^\*\*State:\*\*[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_FENCE_RE = re.compile(r"^```", re.MULTILINE)


def _mask_fenced_blocks(body: str) -> str:
    """Replace fenced code-block contents with spaces, preserving byte offsets.

    Header/state regexes scan the masked body so example snippets inside
    triple-backtick fences cannot pollute parsed unit data, while match
    positions remain valid for slicing the original body.
    """
    fences = list(_FENCE_RE.finditer(body))
    if len(fences) < 2:
        return body
    chars = list(body)
    for i in range(0, len(fences) - 1, 2):
        start = fences[i].start()
        end = fences[i + 1].end()
        for j in range(start, end):
            if chars[j] != "\n":
                chars[j] = " "
    return "".join(chars)


def parse_plan(path: Path) -> Plan:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise ValueError(f"{path}: missing or unterminated frontmatter")
    raw = yaml.safe_load(match.group(1)) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    body = text[match.end() :]

    units = _parse_units(body, frontmatter_units=raw.get("units"))
    extra = {k: v for k, v in raw.items() if k not in _KNOWN_FRONTMATTER_KEYS}

    plan = Plan(
        path=path,
        title=str(raw.get("title", path.stem)),
        type=str(raw.get("type", "feat")),
        status=_coerce_status(raw.get("status", "active"), path),
        date=str(raw.get("date", "")),
        origin=_optional_str(raw.get("origin")),
        parent=_optional_str(raw.get("parent")),
        implemented_in=_optional_str(raw.get("implemented_in")),
        superseded_by=_optional_str(raw.get("superseded_by")),
        abandoned_reason=_optional_str(raw.get("abandoned_reason")),
        verifies=_coerce_str_list(raw.get("verifies")),
        aggregates=_coerce_str_list(raw.get("aggregates")),
        supersedes=_optional_str(raw.get("supersedes")),
        plans=_coerce_str_list(raw.get("plans")),
        units=units,
        extra_frontmatter=extra,
        body=body,
    )
    return plan


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _IndentingDumper(yaml.SafeDumper):
    """SafeDumper that indents list items under their parent key."""

    def increase_indent(  # type: ignore[override]
        self, flow: bool = False, indentless: bool = False
    ) -> None:
        return super().increase_indent(flow, False)


def serialize_plan(plan: Plan) -> str:
    front = _build_frontmatter_dict(plan)
    if isinstance(front.get("date"), str) and _ISO_DATE_RE.match(front["date"]):
        front["date"] = _datetime.date.fromisoformat(front["date"])
    yaml_text = yaml.dump(
        front,
        Dumper=_IndentingDumper,
        sort_keys=False,
        width=100,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip()
    body = _apply_unit_states_to_body(plan.body, plan.units)
    return f"---\n{yaml_text}\n---\n{body}"


def compute_rollup(units: list[Unit]) -> PlanStatus:
    if not units:
        return "active"
    states = [u.state for u in units]
    if all(s in ("complete", "skipped") for s in states) and any(s == "complete" for s in states):
        return "complete"
    if all(s == "skipped" for s in states):
        return "complete"
    if any(s in ("in_progress", "complete") for s in states):
        return "in_progress"
    return "active"


def validate(plan: Plan) -> list[ValidationError]:
    errors: list[ValidationError] = []
    if plan.status not in PLAN_STATUSES:
        errors.append(ValidationError(plan.path, f"invalid plan status: {plan.status!r}"))

    if plan.status == "complete" and not plan.implemented_in:
        errors.append(ValidationError(plan.path, "status=complete requires implemented_in"))
    if plan.status == "superseded" and not plan.superseded_by:
        errors.append(ValidationError(plan.path, "status=superseded requires superseded_by"))
    if plan.status == "abandoned" and not plan.abandoned_reason:
        errors.append(ValidationError(plan.path, "status=abandoned requires abandoned_reason"))

    seen_ids: set[int] = set()
    for unit in plan.units:
        if unit.state not in UNIT_STATES:
            errors.append(
                ValidationError(plan.path, f"unit {unit.id}: invalid state {unit.state!r}")
            )
        if unit.id in seen_ids:
            errors.append(ValidationError(plan.path, f"duplicate unit id: {unit.id}"))
        seen_ids.add(unit.id)
        if unit.state == "skipped" and not unit.skipped_reason:
            errors.append(
                ValidationError(plan.path, f"unit {unit.id}: state=skipped requires a reason")
            )

    rollup = compute_rollup(plan.units)
    if plan.status not in ("superseded", "abandoned", "draft"):
        if plan.units and plan.status != rollup:
            errors.append(
                ValidationError(
                    plan.path,
                    f"plan status={plan.status} disagrees with rollup={rollup}",
                )
            )
    return errors


def set_unit_state(
    plan: Plan,
    unit_id: int,
    state: UnitState,
    *,
    implemented_in: str | None = None,
    skipped_reason: str | None = None,
) -> None:
    if state not in UNIT_STATES:
        raise ValueError(f"invalid unit state: {state!r}")
    target: Unit | None = None
    for unit in plan.units:
        if unit.id == unit_id:
            target = unit
            break
    if target is None:
        raise ValueError(f"unit {unit_id} not found in plan {plan.path}")

    target.state = state
    if state == "complete":
        if implemented_in is not None:
            target.implemented_in = implemented_in
    elif state != "skipped":
        target.implemented_in = None

    if state == "skipped":
        if skipped_reason is not None:
            target.skipped_reason = skipped_reason
    else:
        target.skipped_reason = None

    if plan.status not in ("superseded", "abandoned", "draft"):
        plan.status = compute_rollup(plan.units)


def set_plan_status(
    plan: Plan,
    status: PlanStatus,
    *,
    implemented_in: str | None = None,
    superseded_by: str | None = None,
    abandoned_reason: str | None = None,
) -> None:
    if status not in PLAN_STATUSES:
        raise ValueError(f"invalid plan status: {status!r}")
    plan.status = status
    if status == "complete":
        if implemented_in is not None:
            plan.implemented_in = implemented_in
        for unit in plan.units:
            if unit.state in ("pending", "in_progress"):
                unit.state = "complete"
                if implemented_in is not None and not unit.implemented_in:
                    unit.implemented_in = implemented_in
    else:
        plan.implemented_in = None

    if status == "superseded":
        if superseded_by is not None:
            plan.superseded_by = superseded_by
    else:
        plan.superseded_by = None

    if status == "abandoned":
        if abandoned_reason is not None:
            plan.abandoned_reason = abandoned_reason
    else:
        plan.abandoned_reason = None


def _parse_units(body: str, frontmatter_units: Any) -> list[Unit]:
    units: dict[int, Unit] = {}
    masked = _mask_fenced_blocks(body)

    if isinstance(frontmatter_units, list):
        for entry in frontmatter_units:
            if not isinstance(entry, dict):
                continue
            if "id" not in entry:
                continue
            unit_id = int(entry["id"])
            units[unit_id] = Unit(
                id=unit_id,
                title=str(entry.get("title", "")),
                state=_coerce_unit_state(entry.get("state", "pending")),
                implemented_in=_optional_str(entry.get("implemented_in")),
                skipped_reason=_optional_str(entry.get("skipped_reason")),
            )

    for header_match in _UNIT_HEADER_RE.finditer(masked):
        unit_id = int(header_match.group(1))
        title = header_match.group(2).strip()
        section_start = header_match.end()
        next_match = _UNIT_HEADER_RE.search(masked, section_start)
        section_end = next_match.start() if next_match else len(masked)
        masked_section = masked[section_start:section_end]
        real_section = body[section_start:section_end]
        state_match = _STATE_LINE_RE.search(masked_section)
        body_state: UnitState | None = None
        body_implemented_in: str | None = None
        body_skipped_reason: str | None = None
        if state_match is not None:
            real_text = real_section[state_match.start() : state_match.end()]
            real_match = _STATE_LINE_RE.match(real_text)
            if real_match is not None:
                body_state, body_implemented_in, body_skipped_reason = _parse_state_line(
                    real_match.group(1)
                )

        existing = units.get(unit_id)
        if existing is None:
            unit = Unit(
                id=unit_id,
                title=title,
                state=body_state if body_state is not None else "pending",
                implemented_in=body_implemented_in,
                skipped_reason=body_skipped_reason,
            )
        else:
            unit = existing
            if not unit.title:
                unit.title = title
            if body_state is not None:
                unit.state = body_state
            if body_implemented_in is not None:
                unit.implemented_in = body_implemented_in
            if body_skipped_reason is not None:
                unit.skipped_reason = body_skipped_reason
        units[unit_id] = unit

    return [units[k] for k in sorted(units.keys())]


def _parse_state_line(line: str) -> tuple[UnitState, str | None, str | None]:
    text = line.strip()
    state_word = text.split(None, 1)[0].rstrip(":").lower()
    state: UnitState
    if state_word in UNIT_STATES:
        state = state_word  # type: ignore[assignment]
    else:
        state = "pending"
    implemented_in: str | None = None
    skipped_reason: str | None = None
    lower = text.lower()
    if "implemented in" in lower:
        idx = lower.index("implemented in") + len("implemented in")
        rest = text[idx:].lstrip(": ").strip()
        implemented_in = _strip_trailing_paren(rest) or None
    if state == "skipped":
        sep = text.split("—", 1) if "—" in text else text.split("--", 1)
        if len(sep) > 1:
            skipped_reason = sep[1].strip() or None
    return state, implemented_in, skipped_reason


def _strip_trailing_paren(text: str) -> str:
    paren = text.find(" (")
    if paren > 0:
        return text[:paren].strip()
    return text.strip()


def _build_frontmatter_dict(plan: Plan) -> dict[str, Any]:
    front: dict[str, Any] = {
        "title": plan.title,
        "type": plan.type,
        "status": plan.status,
        "date": plan.date,
    }
    if plan.origin:
        front["origin"] = plan.origin
    if plan.parent:
        front["parent"] = plan.parent
    if plan.supersedes:
        front["supersedes"] = plan.supersedes
    if plan.implemented_in:
        front["implemented_in"] = plan.implemented_in
    if plan.superseded_by:
        front["superseded_by"] = plan.superseded_by
    if plan.abandoned_reason:
        front["abandoned_reason"] = plan.abandoned_reason
    if plan.verifies:
        front["verifies"] = list(plan.verifies)
    if plan.aggregates:
        front["aggregates"] = list(plan.aggregates)
    if plan.plans:
        front["plans"] = list(plan.plans)
    for key, value in plan.extra_frontmatter.items():
        front[key] = value
    if plan.units:
        front["units"] = [_unit_to_dict(u) for u in plan.units]
    return front


def _unit_to_dict(unit: Unit) -> dict[str, Any]:
    data: dict[str, Any] = {"id": unit.id, "title": unit.title, "state": unit.state}
    if unit.implemented_in:
        data["implemented_in"] = unit.implemented_in
    if unit.skipped_reason:
        data["skipped_reason"] = unit.skipped_reason
    return data


def _apply_unit_states_to_body(body: str, units: list[Unit]) -> str:
    state_by_id = {u.id: u for u in units}
    masked = _mask_fenced_blocks(body)
    headers = list(_UNIT_HEADER_RE.finditer(masked))
    if not headers:
        return body

    pieces: list[str] = []
    cursor = 0
    for idx, header in enumerate(headers):
        unit_id = int(header.group(1))
        section_start = header.end()
        section_end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        section = body[section_start:section_end]
        masked_section = masked[section_start:section_end]
        unit = state_by_id.get(unit_id)
        rebuilt_section = (
            _rewrite_state_in_section(section, masked_section, unit) if unit else section
        )
        pieces.append(body[cursor : header.start()])
        pieces.append(body[header.start() : header.end()])
        pieces.append(rebuilt_section)
        cursor = section_end
    pieces.append(body[cursor:])
    return "".join(pieces)


def _rewrite_state_in_section(section: str, masked_section: str, unit: Unit) -> str:
    state_line = _format_state_line(unit)
    state_match = _STATE_LINE_RE.search(masked_section)
    if state_match is not None:
        return section[: state_match.start()] + state_line + section[state_match.end() :]
    leading_newline_count = len(section) - len(section.lstrip("\n"))
    leading = section[:leading_newline_count]
    if not leading:
        leading = "\n"
    return leading + state_line + "\n\n" + section[leading_newline_count:].lstrip("\n")


def _format_state_line(unit: Unit) -> str:
    if unit.state == "complete" and unit.implemented_in:
        return f"**State:** complete — implemented in {unit.implemented_in}"
    if unit.state == "skipped" and unit.skipped_reason:
        return f"**State:** skipped — {unit.skipped_reason}"
    return f"**State:** {unit.state}"


def _coerce_status(value: Any, path: Path) -> PlanStatus:
    if isinstance(value, str) and value in PLAN_STATUSES:
        return value  # type: ignore[return-value]
    return "active"


def _coerce_unit_state(value: Any) -> UnitState:
    if isinstance(value, str) and value in UNIT_STATES:
        return value  # type: ignore[return-value]
    return "pending"


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
