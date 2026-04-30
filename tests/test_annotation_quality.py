"""Tests for annotation quality gates and routing hints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cartograph.annotation.quality import (
    find_low_quality_annotations,
    is_low_quality,
    recommended_tier,
    requeue_low_quality,
)
from cartograph.storage import GraphStore, create_connection


@pytest.fixture
def store(tmp_path: Path) -> GraphStore:
    return GraphStore(create_connection(tmp_path / "quality.db"))


def _node(**overrides):
    node = {
        "kind": "function",
        "name": "good_helper",
        "qualified_name": "mod::good_helper",
        "summary": "The good helper validates incoming inputs.",
        "properties": {"role": "Validation helper"},
    }
    node.update(overrides)
    return node


def _insert_annotation(
    store: GraphStore,
    *,
    name: str,
    summary: str,
    role: str = "Specific role",
    status: str = "annotated",
    properties: dict | None = None,
) -> None:
    props = {"role": role}
    if properties:
        props.update(properties)
    store.upsert_nodes(
        [
            {
                "kind": "function",
                "name": name,
                "qualified_name": f"mod::{name}",
                "file_path": "mod.py",
                "start_line": 1,
                "end_line": 3,
                "language": "python",
                "summary": summary,
                "annotation_status": status,
                "properties": props,
            }
        ]
    )


class TestIsLowQuality:
    def test_well_formed_summary_is_not_low_quality(self):
        is_low, reasons = is_low_quality(_node())
        assert is_low is False
        assert reasons == []

    @pytest.mark.parametrize(
        "phrase",
        [
            "code node representing unknown",
            "unknown implementation",
            "source file container",
            "implementation detail",
            "function implementation",
            "class implementation",
        ],
    )
    def test_placeholder_phrases_are_detected(self, phrase: str):
        is_low, reasons = is_low_quality(_node(summary=f"The good helper has {phrase} details."))
        assert is_low is True
        assert "placeholder_phrase" in reasons

    def test_short_summary_boundary(self):
        low, low_reasons = is_low_quality(
            _node(kind="file", summary="x" * 19, properties={"role": "Source module"})
        )
        ok, ok_reasons = is_low_quality(
            _node(kind="file", summary="x" * 20, properties={"role": "Source module"})
        )
        assert low is True
        assert "summary_too_short" in low_reasons
        assert ok is False
        assert ok_reasons == []

    def test_file_node_gets_name_drop_bypass(self):
        is_low, reasons = is_low_quality(
            _node(
                kind="file",
                name="service.py",
                summary="Collects API request handlers for the service layer.",
                properties={"role": "Request routing module"},
            )
        )
        assert is_low is False
        assert "missing_name_reference" not in reasons

    def test_missing_name_reference_is_detected(self):
        is_low, reasons = is_low_quality(
            _node(summary="Validates incoming inputs for the API layer.")
        )
        assert is_low is True
        assert "missing_name_reference" in reasons

    def test_generic_role_is_detected(self):
        is_low, reasons = is_low_quality(_node(properties={"role": "Function"}))
        assert is_low is True
        assert "generic_role" in reasons


class TestRecommendedTier:
    def test_small_free_function_is_fast(self):
        assert recommended_tier(_node(source="def good_helper():\n    pass\n")) == "fast"

    def test_high_centrality_node_is_strong(self):
        assert recommended_tier(_node(centrality=0.5)) == "strong"

    def test_long_source_is_strong(self):
        assert recommended_tier(_node(source="x" * 3000)) == "strong"

    def test_class_is_strong_without_centrality(self):
        assert recommended_tier(_node(kind="class", centrality=None)) == "strong"


class TestRequeueLowQuality:
    def test_find_low_quality_detects_placeholder_regressions(self, store: GraphStore):
        for i in range(5):
            _insert_annotation(
                store,
                name=f"unknown_{i}",
                summary="Code node representing unknown in the system.",
            )
        _insert_annotation(
            store,
            name="good_node",
            summary="The good node coordinates annotation storage.",
        )

        found = find_low_quality_annotations(store)

        assert len(found) == 5
        assert {n["name"] for n in found} == {f"unknown_{i}" for i in range(5)}
        assert all("placeholder_phrase" in n["reasons"] for n in found)

    def test_dry_run_does_not_mutate_then_requeue_flips_status(self, store: GraphStore):
        _insert_annotation(
            store,
            name="unknown_node",
            summary="Code node representing unknown in the system.",
        )

        dry = requeue_low_quality(store, dry_run=True)
        assert dry.low_quality == 1
        assert dry.requeued == 0
        assert store.get_node_by_name("mod::unknown_node")["annotation_status"] == "annotated"

        live = requeue_low_quality(store, dry_run=False)
        assert live.low_quality == 1
        assert live.requeued == 1

        node = store.get_node_by_name("mod::unknown_node")
        assert node["annotation_status"] == "pending"
        props = node["properties"]
        if isinstance(props, str):
            props = json.loads(props)
        assert props["requeue_count"] == 1
        assert "placeholder_phrase" in props["requeue_reason"]

    def test_requeue_cap_marks_failed(self, store: GraphStore):
        _insert_annotation(
            store,
            name="looping_node",
            summary="Code node representing unknown in the system.",
            properties={"requeue_count": 3},
        )

        result = requeue_low_quality(store, dry_run=False)

        assert result.low_quality == 1
        assert result.requeued == 0
        assert result.failed == 1
        node = store.get_node_by_name("mod::looping_node")
        assert node["annotation_status"] == "failed"
