"""Shared helpers for token-aware MCP tool responses."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Literal

ResponseShape = Literal["compact", "standard", "full"]
VALID_RESPONSE_SHAPES: set[str] = {"compact", "standard", "full"}
TRUNCATED_FLAG = "truncated_items"


try:  # pragma: no cover - tiktoken is optional in this project.
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")
    _APPROXIMATION_METHOD = "tiktoken"
except Exception:  # noqa: BLE001 - optional dependency can fail several ways.
    _ENCODER = None
    _APPROXIMATION_METHOD = "char_div_4"


@dataclass(frozen=True)
class CursorState:
    """Decoded pagination cursor state."""

    offset: int
    query_hash: str


def validate_response_shape(response_shape: str) -> dict[str, str] | None:
    """Return an MCP error payload when *response_shape* is unsupported."""
    if response_shape in VALID_RESPONSE_SHAPES:
        return None
    return {
        "error": f"unknown response_shape '{response_shape}'. Use 'compact', 'standard', or 'full'."
    }


def estimate_tokens(payload: Any) -> int:
    """Estimate token usage for a JSON-serialisable payload."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if _ENCODER is not None:
        return len(_ENCODER.encode(text))
    return max(1, (len(text) + 3) // 4)


def actual_chars(payload: Any) -> int:
    """Return exact JSON character count for diagnostics."""
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))


def approximation_method() -> str:
    """Return the token estimator name used in budget metadata."""
    return _APPROXIMATION_METHOD


def compact_text(value: Any, limit: int = 160) -> str | None:
    """Return *value* as a single-line string capped at *limit* characters."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def query_hash(tool_name: str, params: dict[str, Any]) -> str:
    """Hash stable call identity for cursor validation."""
    identity = {"tool": tool_name, **params}
    encoded = json.dumps(identity, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def encode_cursor(offset: int, query_hash_value: str) -> str:
    """Encode an opaque cursor from offset and query hash."""
    payload = json.dumps({"offset": offset, "query_hash": query_hash_value}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str | None) -> CursorState | None | dict[str, str]:
    """Decode a cursor, returning an MCP error payload for malformed cursors."""
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        payload = json.loads(raw)
        offset = int(payload["offset"])
        cursor_hash = str(payload["query_hash"])
    except Exception:  # noqa: BLE001 - malformed cursors should not escape.
        return {"error": "invalid_cursor", "message": "Cursor could not be decoded."}
    if offset < 0:
        return {"error": "invalid_cursor", "message": "Cursor offset must be non-negative."}
    return CursorState(offset=offset, query_hash=cursor_hash)


def cursor_offset(cursor: str | None) -> int:
    """Return decoded cursor offset, or 0 when the cursor is absent/malformed."""
    decoded = decode_cursor(cursor)
    if isinstance(decoded, CursorState):
        return decoded.offset
    return 0


def paginate_items(
    items: list[dict[str, Any]],
    *,
    cursor: str | None,
    page_size: int | None,
    query_hash_value: str,
) -> tuple[list[dict[str, Any]], str | None, dict[str, str] | None]:
    """Return one page of items, next cursor, and optional error."""
    decoded = decode_cursor(cursor)
    if isinstance(decoded, dict):
        return [], None, decoded
    offset = decoded.offset if decoded is not None else 0
    if decoded is not None and decoded.query_hash != query_hash_value:
        return [], None, {"error": "invalid_cursor", "message": "Cursor does not match this query."}

    if page_size is None or page_size <= 0:
        page_size = max(0, len(items) - offset)

    page = items[offset : offset + page_size]
    next_offset = offset + len(page)
    next_cursor = encode_cursor(next_offset, query_hash_value) if next_offset < len(items) else None
    return page, next_cursor, None


def _list_paths(value: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    paths: list[tuple[Any, ...]] = []
    if isinstance(value, list):
        paths.append(path)
        for index, item in enumerate(value):
            paths.extend(_list_paths(item, (*path, index)))
    elif isinstance(value, dict):
        for key, item in value.items():
            paths.extend(_list_paths(item, (*path, key)))
    return paths


def _get_path(value: Any, path: tuple[Any, ...]) -> Any:
    current = value
    for part in path:
        current = current[part]
    return current


def apply_token_budget(payload: dict[str, Any], token_budget: int | None) -> dict[str, Any]:
    """Trim list payloads until the response fits within *token_budget*."""
    if token_budget is None:
        return payload

    budget = max(1, int(token_budget))
    result = copy.deepcopy(payload)
    truncated_items = 0

    def with_metadata() -> dict[str, Any]:
        candidate = copy.deepcopy(result)
        candidate[TRUNCATED_FLAG] = truncated_items
        candidate["budget_used"] = estimate_tokens(candidate)
        candidate["budget_remaining"] = max(0, budget - candidate["budget_used"])
        candidate["approximation_method"] = approximation_method()
        candidate["actual_chars"] = actual_chars(candidate)
        return candidate

    current = with_metadata()
    while estimate_tokens(current) > budget:
        list_paths = [
            path for path in _list_paths(result) if isinstance(_get_path(result, path), list)
        ]
        non_empty_paths = [path for path in list_paths if _get_path(result, path)]
        if not non_empty_paths:
            break
        longest_path = max(non_empty_paths, key=lambda path: len(_get_path(result, path)))
        _get_path(result, longest_path).pop()
        truncated_items += 1
        current = with_metadata()

    current["budget_used"] = estimate_tokens(current)
    current["budget_remaining"] = max(0, budget - current["budget_used"])
    current["actual_chars"] = actual_chars(current)
    return current
