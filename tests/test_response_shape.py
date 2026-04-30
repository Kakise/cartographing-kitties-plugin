from __future__ import annotations

from cartograph.server.response_shape import (
    apply_token_budget,
    decode_cursor,
    encode_cursor,
    estimate_tokens,
    paginate_items,
    query_hash,
    validate_response_shape,
)


def test_validate_response_shape_accepts_known_shapes() -> None:
    assert validate_response_shape("compact") is None
    assert validate_response_shape("standard") is None
    assert validate_response_shape("full") is None


def test_validate_response_shape_rejects_unknown_shape() -> None:
    assert validate_response_shape("bogus") == {
        "error": "unknown response_shape 'bogus'. Use 'compact', 'standard', or 'full'."
    }


def test_cursor_round_trip_and_pagination() -> None:
    qhash = query_hash("search", {"query": "User", "kind": None})
    cursor = encode_cursor(2, qhash)
    state = decode_cursor(cursor)
    assert not isinstance(state, dict)
    assert state is not None
    assert state.offset == 2
    assert state.query_hash == qhash

    items = [{"value": i} for i in range(5)]
    page, next_cursor, error = paginate_items(
        items, cursor=None, page_size=2, query_hash_value=qhash
    )
    assert error is None
    assert page == [{"value": 0}, {"value": 1}]
    assert next_cursor is not None

    second_page, _, error = paginate_items(
        items, cursor=next_cursor, page_size=2, query_hash_value=qhash
    )
    assert error is None
    assert second_page == [{"value": 2}, {"value": 3}]


def test_cursor_rejects_mismatched_query_hash() -> None:
    cursor = encode_cursor(2, "old")
    _, _, error = paginate_items([{"value": 1}], cursor=cursor, page_size=1, query_hash_value="new")
    assert error == {"error": "invalid_cursor", "message": "Cursor does not match this query."}


def test_apply_token_budget_truncates_list_payloads() -> None:
    payload = {
        "items": [{"text": "x" * 200} for _ in range(10)],
        "summary": "budgeted",
    }

    result = apply_token_budget(payload, 180)

    assert estimate_tokens(result) <= 180
    assert result["truncated_items"] > 0
    assert result["budget_used"] <= 180
    assert result["budget_remaining"] >= 0
    assert result["approximation_method"] in {"tiktoken", "char_div_4"}
