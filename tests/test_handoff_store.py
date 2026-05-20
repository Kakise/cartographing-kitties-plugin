"""Tests for the agent-handoff store DAO."""

from __future__ import annotations

from pathlib import Path

import pytest

from cartograph.memory import (
    DEFAULT_HANDOFF_TTL_SECONDS,
    LONG_RUNNING_HANDOFF_TTL_SECONDS,
    expire_handoffs,
    get_handoff,
    stage_handoff,
)
from cartograph.storage import GraphStore, create_connection


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    conn = create_connection(tmp_path / "test.db")
    return GraphStore(conn)


def _payload(name: str = "demo") -> dict[str, object]:
    return {
        "agent": name,
        "role": "research",
        "findings_or_observations": [{"section": "Architecture", "body": "..."}],
        "summary": "demo summary",
        "confidence": 0.9,
        "sources": [],
        "needs_more_context": [],
    }


def test_stage_returns_unique_run_ids(store: GraphStore) -> None:
    a = stage_handoff(store, "session-1", "agent-a", "research", _payload("a"))
    b = stage_handoff(store, "session-1", "agent-a", "research", _payload("a"))
    assert a != b


def test_get_handoff_round_trip(store: GraphStore) -> None:
    payload = _payload("librarian-kitten-researcher")
    run_id = stage_handoff(
        store, "session-7", "librarian-kitten-researcher", "research", payload, now=1_000_000
    )
    record = get_handoff(store, run_id, now=1_000_001)

    assert record is not None
    assert record.run_id == run_id
    assert record.session_id == "session-7"
    assert record.agent_name == "librarian-kitten-researcher"
    assert record.role == "research"
    assert record.payload == payload
    assert record.expires_at == 1_000_000 + DEFAULT_HANDOFF_TTL_SECONDS


def test_get_handoff_returns_none_for_unknown_run_id(store: GraphStore) -> None:
    assert get_handoff(store, "deadbeef") is None


def test_expired_records_are_treated_as_missing(store: GraphStore) -> None:
    run_id = stage_handoff(
        store, "session-x", "expert-kitten-correctness", "review", _payload(), now=100
    )
    # Default TTL is 24h; query well past that.
    later = 100 + DEFAULT_HANDOFF_TTL_SECONDS + 10
    assert get_handoff(store, run_id, now=later) is None


def test_long_running_ttl_keeps_records_for_a_week(store: GraphStore) -> None:
    run_id = stage_handoff(
        store,
        "session-long",
        "librarian-kitten-impact",
        "research",
        _payload(),
        ttl_seconds=LONG_RUNNING_HANDOFF_TTL_SECONDS,
        now=0,
    )
    # Six days later — still alive.
    assert get_handoff(store, run_id, now=6 * 86_400) is not None
    # Eight days later — gone.
    assert get_handoff(store, run_id, now=8 * 86_400) is None


def test_expire_handoffs_deletes_only_stale_records(store: GraphStore) -> None:
    fresh = stage_handoff(store, "s", "a-fresh", "research", _payload(), now=1_000)
    stale = stage_handoff(store, "s", "a-stale", "review", _payload(), now=1_000)

    # Fast-forward past the stale entry's expiry but well before the fresh
    # one's by re-staging fresh with a very long TTL.
    fresh = stage_handoff(
        store,
        "s",
        "a-fresh-replacement",
        "research",
        _payload(),
        ttl_seconds=LONG_RUNNING_HANDOFF_TTL_SECONDS,
        now=1_000,
    )

    deleted = expire_handoffs(store, now=1_000 + DEFAULT_HANDOFF_TTL_SECONDS + 1)
    assert deleted >= 1

    # The fresh long-TTL record survives; the stale one is gone.
    assert get_handoff(store, fresh, now=1_001) is not None
    assert get_handoff(store, stale, now=1_001) is None


def test_invalid_role_rejected(store: GraphStore) -> None:
    with pytest.raises(ValueError, match="Invalid handoff role"):
        stage_handoff(store, "s", "agent", "manager", _payload())


def test_zero_ttl_rejected(store: GraphStore) -> None:
    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        stage_handoff(store, "s", "agent", "research", _payload(), ttl_seconds=0)
