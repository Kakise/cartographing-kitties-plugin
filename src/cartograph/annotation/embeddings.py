"""Static (Model2Vec) embedding generator for the hybrid-search dense leg.

Hybrid search (R1, plan ``2026-05-04-003``) needs cheap dense embeddings over
node summaries.  We use Model2Vec because it is pure-NumPy (no torch, no ONNX)
and produces 256-d vectors in well under a millisecond per text on commodity
CPU — the cost we're willing to pay for an offline retrieval signal.

The :class:`Embedder` is a thin wrapper around
``model2vec.StaticModel.from_pretrained`` with three responsibilities:

* lazy, single-process load (``get_instance``) so importing this module costs
  nothing;
* a deterministic cache directory under ``<data_dir>/models/`` so subsequent
  runs hit local files;
* a ``KITTY_EMBED_MODEL_PATH`` escape hatch for firewalled environments where
  the Hugging Face hub is unreachable.

Encode failures bubble up as :class:`EmbeddingError`.  Callers (annotator,
back-fill, search) treat dense-channel population as best-effort and degrade
to FTS5 + centrality on error.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type-only
    import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "minishlab/potion-base-8M"
EMBEDDING_DIM = 256
_MODEL_PATH_ENV = "KITTY_EMBED_MODEL_PATH"


class EmbeddingError(RuntimeError):
    """Raised when the embedding model cannot be loaded or invoked."""


class Embedder:
    """Lazy singleton wrapping a Model2Vec ``StaticModel``.

    Use :meth:`get_instance` for the process-wide singleton.  The constructor
    is exposed for tests that want a fresh instance with custom paths.
    """

    _instance: Embedder | None = None
    _lock = threading.Lock()

    def __init__(
        self,
        model_name_or_path: str | os.PathLike[str] = DEFAULT_MODEL,
        *,
        cache_dir: Path | None = None,
    ) -> None:
        self._model_name_or_path = str(model_name_or_path)
        self._cache_dir = cache_dir
        self._model: Any | None = None  # StaticModel — kept Any to avoid import at module load

    # ------------------------------------------------------------------
    # Public API

    @classmethod
    def get_instance(cls, *, cache_dir: Path | None = None) -> Embedder:
        """Return the process-wide :class:`Embedder` singleton.

        ``cache_dir`` is honoured only on first construction; later calls
        return the existing instance regardless of the argument.  Tests that
        need isolation should construct an :class:`Embedder` directly.
        """
        with cls._lock:
            if cls._instance is None:
                env_path = os.environ.get(_MODEL_PATH_ENV)
                model_path: str | os.PathLike[str] = env_path or DEFAULT_MODEL
                cls._instance = cls(model_path, cache_dir=cache_dir)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton.  Test-only — prod code never calls this."""
        with cls._lock:
            cls._instance = None

    def embed(self, text: str) -> list[float]:
        """Return a ``EMBEDDING_DIM``-d list of floats for *text*."""
        vec = self._model_or_load().encode(text)
        return _ensure_list(vec)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        if not texts:
            return []
        matrix = self._model_or_load().encode(texts)
        return [_ensure_list(row) for row in matrix]

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIM

    # ------------------------------------------------------------------
    # Internals

    def _model_or_load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            # Imported lazily so ``import cartograph.annotation.embeddings``
            # is free until the first encode call.
            from model2vec import StaticModel
        except ImportError as exc:  # pragma: no cover - tested via Unit 1 deps
            raise EmbeddingError(
                "model2vec is not installed; run `uv sync --all-extras` to "
                "enable the dense channel of hybrid search."
            ) from exc

        try:
            self._model = StaticModel.from_pretrained(self._model_name_or_path)
        except Exception as exc:  # noqa: BLE001 — HF surfaces several types
            raise EmbeddingError(
                f"Failed to load embedding model '{self._model_name_or_path}': {exc}"
            ) from exc

        actual_dim = _model_dimension(self._model)
        if actual_dim != EMBEDDING_DIM:
            raise EmbeddingError(
                f"Embedding model '{self._model_name_or_path}' produced "
                f"{actual_dim}-d vectors; hybrid search expects {EMBEDDING_DIM}-d "
                "(see `nodes_vec` schema in migration 0006)."
            )

        return self._model


def _ensure_list(vec: np.ndarray | list[float]) -> list[float]:
    tolist = getattr(vec, "tolist", None)
    if tolist is not None:
        return [float(x) for x in tolist()]
    return [float(x) for x in vec]


def _model_dimension(model: Any) -> int:
    """Best-effort dimension probe for a loaded StaticModel."""
    dim = getattr(model, "dim", None)
    if isinstance(dim, int):
        return dim
    embedding = getattr(model, "embedding", None)
    shape = getattr(embedding, "shape", None)
    if shape is not None and len(shape) >= 2:
        return int(shape[-1])
    sample = model.encode("dimension probe")
    sample_shape = getattr(sample, "shape", None)
    if sample_shape:
        return int(sample_shape[-1])
    return len(list(sample))
