"""Reusable JSON Schema fragments for MCP tool responses."""

from __future__ import annotations

from typing import Any

NODE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "qualified_name": {"type": "string"},
        "kind": {"type": "string"},
        "role": {"type": "string"},
        "summary": {"type": ["string", "null"]},
        "centrality": {"type": ["number", "null"]},
    },
    "required": ["qualified_name", "kind"],
    "additionalProperties": True,
}

BUDGET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "truncated_items": {"type": "integer"},
        "budget_used": {"type": "integer"},
        "budget_remaining": {"type": "integer"},
        "approximation_method": {"type": "string"},
        "actual_chars": {"type": "integer"},
    },
    "additionalProperties": True,
}

PAGED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "next_cursor": {"type": ["string", "null"]},
    },
    "additionalProperties": True,
}
