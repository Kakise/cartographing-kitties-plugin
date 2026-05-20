"""Tests for cartograph.annotation.embeddings (Unit 2 of hybrid-search plan).

These tests exercise the live ``minishlab/potion-base-8M`` model.  CI machines
prefetch the model on the first run; subsequent runs hit the local cache.  If
the network is unavailable and no cached model exists the tests are skipped
via the ``model2vec``/HuggingFace error path — see the ``EmbeddingError``
contract.
"""

from __future__ import annotations

import sys

import pytest

from cartograph.annotation.embeddings import (
    DEFAULT_MODEL,
    EMBEDDING_DIM,
    Embedder,
    EmbeddingError,
)


@pytest.fixture(autouse=True)
def _reset_embedder_singleton():
    Embedder.reset_instance()
    yield
    Embedder.reset_instance()


def _load_embedder_or_skip() -> Embedder:
    pytest.importorskip("model2vec")
    embedder = Embedder(DEFAULT_MODEL)
    try:
        embedder.embed("warm up")
    except EmbeddingError as exc:
        pytest.skip(f"Embedding model unavailable: {exc}")
    return embedder


class TestEmbedder:
    def test_embed_returns_correct_dimension(self):
        embedder = _load_embedder_or_skip()
        vec = embedder.embed("retry on failure with exponential backoff")
        assert isinstance(vec, list)
        assert len(vec) == EMBEDDING_DIM
        assert all(isinstance(x, float) for x in vec)

    def test_embed_batch_returns_one_vector_per_text(self):
        embedder = _load_embedder_or_skip()
        out = embedder.embed_batch(["alpha", "beta", "gamma"])
        assert len(out) == 3
        for vec in out:
            assert len(vec) == EMBEDDING_DIM

    def test_embed_batch_handles_empty(self):
        embedder = _load_embedder_or_skip()
        assert embedder.embed_batch([]) == []

    def test_embed_is_deterministic(self):
        embedder = _load_embedder_or_skip()
        a = embedder.embed("graph centrality")
        b = embedder.embed("graph centrality")
        assert a == b

    def test_get_instance_returns_singleton(self):
        pytest.importorskip("model2vec")
        first = Embedder.get_instance()
        second = Embedder.get_instance()
        assert first is second

    def test_get_instance_is_lazy_no_torch_imported(self):
        """Verifies that loading the static model does NOT pull in torch.

        The whole point of choosing model2vec was to avoid the
        ``sentence-transformers``/``torch`` install footprint; this test
        guards against accidental re-introduction via a transitive import.
        """
        pytest.importorskip("model2vec")
        embedder = Embedder.get_instance()
        try:
            embedder.embed("guard against torch")
        except EmbeddingError as exc:
            pytest.skip(f"Embedding model unavailable: {exc}")
        assert "torch" not in sys.modules, (
            "torch must not be importable after Embedder.embed; check that no "
            "transformer-based dependency was reintroduced into the dense channel."
        )

    def test_load_failure_raises_embedding_error(self, tmp_path):
        """A missing local path should surface as EmbeddingError, not raw HF errors."""
        pytest.importorskip("model2vec")
        bad_path = tmp_path / "no-such-model"
        embedder = Embedder(str(bad_path))
        with pytest.raises(EmbeddingError):
            embedder.embed("anything")

    def test_dimension_property(self):
        pytest.importorskip("model2vec")
        embedder = Embedder(DEFAULT_MODEL)
        assert embedder.dimension == EMBEDDING_DIM
