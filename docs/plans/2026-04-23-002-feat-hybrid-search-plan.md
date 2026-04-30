---
title: Hybrid Semantic + Lexical + Graph Search (R1)
type: feat
status: active
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
parent: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
requirement: R1
units:
  - id: 1
    title: Dependency + migration scaffolding
    state: pending
  - id: 2
    title: Embedding generator module
    state: pending
  - id: 3
    title: Graph-centrality channel
    state: pending
  - id: 4
    title: RRF fusion in `GraphStore.search`
    state: pending
  - id: 5
    title: Embedding generation at annotation time
    state: pending
  - id: 6
    title: Evaluation harness & recall measurement
    state: pending
  - id: 7
    title: Documentation
    state: pending
---

# Hybrid Search — Implementation Plan (R1)

## Overview

Extend `search` into a three-channel retrieval pipeline: FTS5 (existing), dense embeddings over
summaries + node names, and graph-centrality boost. Fuse via Reciprocal Rank Fusion (RRF). Ship
with `sqlite-vec` as the vector store so SQLite remains the single substrate. Success: recall@10
beats current FTS5-only baseline by ≥15% on a held-out query set.

## Problem Frame

`cartograph.storage.graph_store::GraphStore::search` today is FTS5-only over `name`,
`qualified_name`, and `summary`. This fails on paraphrastic queries ("retry on failure" → code
tagged `backoff`, `resilience`, `exponential_wait`). Hybrid retrieval in the 2026 literature
consistently outperforms lexical-only by 10–30% recall. The graph and lexical legs are already in
place; adding a dense leg and fusing the three closes the gap without leaving SQLite.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R1.a — Dense embeddings persisted alongside nodes | Unit 2 |
| R1.b — Graph-centrality leg fused into ranking | Unit 3 (consumes R6 output) |
| R1.c — RRF fusion of three channels in `search` | Unit 4 |
| R1.d — Annotation pipeline generates embeddings incrementally | Unit 5 |
| R1.e — Measurable ≥15% recall@10 improvement on held-out queries | Unit 6 |

## Scope Boundaries

- **In scope:** `sqlite-vec` integration, embedding-generation pipeline, `search` tool extension,
  RRF fusion implementation, a held-out evaluation harness under `tests/evaluation/`.
- **Out of scope:** embeddings on code chunks (summaries-only for v1 per brainstorm deferral);
  query-side query-understanding/rewriting; re-indexing the existing 946 nodes — embeddings are
  generated lazily during the next annotation pass or on demand via `annotation_status`-driven
  fill.

## Context & Research

### Annotation Status

- Total nodes: 946, annotated: 946 (100%), pending: 0, stale: 0.
- 100% annotation coverage means we can back-fill embeddings in a single batch pass.

### Target Files

- `src/cartograph/storage/schema.py` — add embedding virtual-table reference.
- `src/cartograph/storage/migrations/0003_hybrid_search.sql` — **new migration**.
- `src/cartograph/storage/graph_store.py::GraphStore::search` — replace with 3-channel fused impl.
- `src/cartograph/server/tools/query.py::search` — extend signature with `mode` toggle + limit.
- `src/cartograph/annotation/annotator.py::write_annotations` — emit embeddings on write.
- `src/cartograph/annotation/embeddings.py` — **new module** for embedding generation.
- `tests/test_hybrid_search.py` — **new test module**.
- `tests/evaluation/query_set.json` — **new** held-out query fixtures.

### Key Symbol Details

- `GraphStore.search(query, kind, limit)` currently runs `SELECT ... FROM nodes_fts WHERE
  nodes_fts MATCH ? ORDER BY rank LIMIT ?`. Signature preserved; internal implementation swapped.
- `write_annotations(...)` in `annotation/annotator.py` is the single write point for summary
  updates — embedding generation hooks cleanly here.
- `rank_by_in_degree` / `rank_by_transitive` already exist on `GraphStore`; the graph-boost
  channel calls one of these to produce a centrality score per candidate.

## Key Technical Decisions

### Embedding model: `BAAI/bge-small-en-v1.5` (384-dim, ~33 MB, CPU-fast)

Rationale:
- **Zero-service:** runs locally via `sentence-transformers` on CPU. No ONNX dependency.
- **Size:** 33 MB (~5 MB quantized). Small enough to bundle or pull once on first run.
- **Quality:** leads MTEB code-adjacent benchmarks among <100 MB models; code-tuned
  `CodeRankEmbed` is stronger but ~600 MB — defer for v2 per the brainstorm's open question.
- **Dimensionality:** 384 fits SQLite page sizes cleanly; `sqlite-vec` handles 384 natively.

v2 candidate: upgrade to `jina-embeddings-v2-base-code` (768-dim, code-aware) once v1 ships
baseline metrics and the model-swap migration path is proven.

### Fusion algorithm: Reciprocal Rank Fusion with k=60

`score(d) = Σ_c (1 / (k + rank_c(d)))` for each channel c. k=60 is the standard-literature default
(Cormack et al. 2009); no per-channel weight tuning required.

### `sqlite-vec` integration: loaded at connection time

- Add `sqlite-vec` to dependencies in `pyproject.toml`.
- In `cartograph.storage.connection::create_connection`, call `conn.enable_load_extension(True)` and
  `sqlite_vec.load(conn)` once before running migrations. Gracefully disable the dense channel and
  log a warning if load fails (platform fallback).
- Virtual table: `CREATE VIRTUAL TABLE nodes_vec USING vec0(embedding float[384])` keyed by
  `nodes.id`.

### Degraded mode (sqlite-vec unavailable)

- `GraphStore.search` checks a `_vec_available` flag. If false, fuse only FTS5 + centrality. Log
  `"Hybrid search in degraded mode: dense channel disabled (sqlite-vec not loaded)"`. Tests exercise
  both paths.

## Open Questions

### Resolve Before Implementing

- **Should the `search` tool expose a `mode` parameter (`hybrid` | `lexical` | `dense`)?**
  Recommendation: yes, defaulting to `hybrid`. Agents that want deterministic lexical behavior
  keep it; researchers can A/B on a flag. Alternative: keep it implicit and always hybrid.
  **Decision needed before Unit 4.**

- **Do we ship the held-out query fixture in the repo or keep it external?**
  Recommendation: in-repo under `tests/evaluation/` with ~40 queries hand-authored against the
  current graph. Keeps the recall@10 measurement reproducible in CI.

### Defer

- Code-chunk embeddings vs. summary-only. Measure summary-only first; revisit after Unit 6.

## Implementation Units

### Unit 1 — Dependency + migration scaffolding

**State:** pending

- [ ] Add `sqlite-vec>=0.1.1` to `pyproject.toml` dependencies.
- [ ] Add `sentence-transformers>=3.0.0` to `pyproject.toml` dependencies.
- [ ] Write `src/cartograph/storage/migrations/0003_hybrid_search.sql`:
      `CREATE VIRTUAL TABLE IF NOT EXISTS nodes_vec USING vec0(embedding float[384])`.
- [ ] Update `cartograph.storage.connection::create_connection` to load the `sqlite_vec` extension
      with try/except fallback.

**Files:**
- `pyproject.toml` (modify)
- `src/cartograph/storage/migrations/0003_hybrid_search.sql` (new)
- `src/cartograph/storage/connection.py` (modify)

**Verification:**
- `uv sync --all-extras` succeeds.
- `uv run python -c "import sqlite_vec; import sentence_transformers"` succeeds.
- `uv run pytest tests/test_storage.py` still green; new test asserts that opening a fresh
  GraphStore creates the `nodes_vec` table when sqlite-vec is available and logs a warning
  otherwise.

**Test scenarios:**
- Happy: `sqlite_vec.load()` succeeds → `_vec_available = True` → `nodes_vec` table exists.
- Error: simulated `load()` failure → `_vec_available = False` → GraphStore still functional.

### Unit 2 — Embedding generator module

**State:** pending

- [ ] Create `src/cartograph/annotation/embeddings.py` exporting:
      - `Embedder.get_instance()` → singleton loading `bge-small-en-v1.5` lazily.
      - `Embedder.embed(text: str) -> list[float]` (dim=384).
      - `Embedder.embed_batch(texts: list[str]) -> list[list[float]]` (batched).
- [ ] Model is loaded on first call, not at import time. Downloaded to `.pawprints/models/` so
      repeated runs don't re-fetch.

**Files:**
- `src/cartograph/annotation/embeddings.py` (new)

**Verification:**
- Unit test with a tiny text corpus confirms vectors are 384-d, normalized, and deterministic.

**Test scenarios:**
- Happy: `embed("foo")` returns 384-d list; `embed_batch(["foo", "bar"])` returns 2 vectors.
- Cold start: model downloads on first call; second call uses cached model.
- Error: embedding failure (e.g., disk full) raises `EmbeddingError` that `write_annotations`
  catches.

### Unit 3 — Graph-centrality channel

**State:** pending

- [ ] Add `GraphStore.centrality_score(node_ids: list[int]) -> dict[int, float]`.
- [ ] Implementation reuses `rank_by_in_degree` (preferred; transitive is O(N²)). Normalize scores
      to [0, 1] by dividing by the max in-degree over the full graph (cache this value on the
      `graph_meta` table, invalidated on `increment_graph_version`).
- [ ] Depends on **R6** if R6 lands first (R6 adds a cached `centrality` column). If R6 is not
      yet shipped, compute inline with caching in memory per-process.

**Files:**
- `src/cartograph/storage/graph_store.py` (modify)

**Verification:**
- Unit test asserts centrality scores are in [0, 1] and that higher-in-degree nodes get higher
  scores.

### Unit 4 — RRF fusion in `GraphStore.search`

**State:** pending

- [ ] Replace the body of `GraphStore.search(query, kind=None, limit=20)` with:
      1. Run FTS5 channel → ranked list of (node_id, rank_fts).
      2. If `_vec_available`, compute `query_vec = Embedder.embed(query)`, run
         `SELECT rowid FROM nodes_vec WHERE embedding MATCH ? ORDER BY distance LIMIT ?`
         with `3 × limit` to keep the fusion pool deep → ranked list of (node_id, rank_vec).
      3. Collect union of node_ids; call `centrality_score` → dict of (node_id, score).
         Rank by score descending → ranked list of (node_id, rank_graph).
      4. Apply RRF with k=60 across whichever channels are available.
      5. Filter by `kind` if provided, then take top `limit`.
      6. Materialize results via existing `_row_to_dict`-like serialization.
- [ ] Add `mode: Literal["hybrid", "lexical", "dense"] = "hybrid"` parameter.

**Files:**
- `src/cartograph/storage/graph_store.py::GraphStore::search` (modify)
- `src/cartograph/server/tools/query.py::search` (modify signature to pass `mode`)

**Patterns to follow:**
- Preserve current return shape (see `_summarise_node` in `query.py`) so downstream tools and
  tests don't change.

**Test scenarios:**
- Happy: query matching via lexical only still returns expected node at top; query matching via
  semantic only (paraphrased) returns the correct node within top-10 (was outside in FTS5-only).
- Edge: empty query string → returns empty list without errors.
- Edge: `mode="lexical"` exactly reproduces the old FTS5 result order.
- Edge: `kind="class"` filter applied post-fusion yields only classes.
- Degraded: `_vec_available=False` → fusion skips dense channel, `mode="dense"` returns empty
  with a clear message.

### Unit 5 — Embedding generation at annotation time

**State:** pending

- [ ] Modify `cartograph.annotation.annotator::write_annotations` to:
      1. For each successfully written annotation, compute `Embedder.embed(summary + " " +
         qualified_name)` (combining both gives better recall on name-heavy queries).
      2. Upsert into `nodes_vec` via `INSERT OR REPLACE INTO nodes_vec(rowid, embedding) VALUES
         (?, ?)`.
- [ ] Add a one-shot back-fill: `uv run python -m cartograph.annotation.embeddings_backfill`
      iterates over all annotated nodes missing a vector and fills them. Idempotent.

**Files:**
- `src/cartograph/annotation/annotator.py` (modify)
- `src/cartograph/annotation/embeddings_backfill.py` (new)

**Test scenarios:**
- Happy: annotating a new node writes both `summary` and a matching row in `nodes_vec`.
- Happy: back-fill on an existing DB with 946 annotated nodes produces 946 vectors.
- Error: if `Embedder.embed` fails, annotation persistence still succeeds; a warning log is
  emitted; node flagged for retry via standard stale-annotation mechanism.

### Unit 6 — Evaluation harness & recall measurement

**State:** pending

- [ ] Create `tests/evaluation/query_set.json` with ~40 queries. Schema:
      `{"query": "...", "expected_qualified_names": ["...", "..."]}`. Cover: exact name matches,
      paraphrases, intent phrases, anti-pattern queries.
- [ ] Create `tests/evaluation/test_hybrid_recall.py` that:
      1. Asserts recall@10 for `mode="lexical"` (baseline).
      2. Asserts recall@10 for `mode="hybrid"` is ≥15% absolute improvement.
      3. Runs under the standard pytest job but is marked `@pytest.mark.evaluation` so it can
         be skipped in fast CI if needed.
- [ ] Ship baseline + target numbers in the plan's handoff note.

**Files:**
- `tests/evaluation/query_set.json` (new)
- `tests/evaluation/test_hybrid_recall.py` (new)
- `tests/evaluation/__init__.py` (new, empty)

**Test scenarios:**
- Happy: hybrid beats lexical by ≥15% on the fixture set.
- Edge: recall@1 and recall@5 are also reported (not asserted) so we have the full curve.

### Unit 7 — Documentation

**State:** pending

- [ ] Update `README.md` "Features" section to describe hybrid search.
- [ ] Update `CLAUDE.md` MCP tool table so the `search` description notes "hybrid (lexical + dense
      + graph) fused via RRF".
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md` with the new `mode`
      parameter.

**Files:**
- `README.md`, `CLAUDE.md`, `plugins/kitty/skills/kitty/references/tool-reference.md` (modify)

## System-Wide Impact

- **Agents consuming `search`:** all `librarian-kitten-*` and `expert-kitten-*` agents, plus every
  skill that delegates to them. Signature additive (new optional `mode` param). No breaking
  changes.
- **Graph DB size:** +~1.5 MB per 1000 nodes at 384-d float32 (346 KB total for 946 nodes). Row
  per node in `nodes_vec`.
- **First-run latency:** model download (~33 MB) on first annotation or first search. One-time.
- **Per-query latency:** FTS5 ~5 ms + dense ~20 ms (384-d over 1000s of vectors) + centrality
  lookup ~2 ms + fusion ~1 ms ≈ 30 ms p50. Well under the existing 100 ms test assertion.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| `sqlite-vec` load failure on exotic platforms | Degraded mode disables dense channel; test covers |
| Model download fails behind a firewall | Allow `KITTY_EMBED_MODEL_PATH` env var to point at a local directory; document |
| RRF tuning produces regressions vs. pure FTS5 on very short/exact queries | `mode="lexical"` escape hatch; measure recall@1 specifically in eval |
| Back-fill on a huge repo takes too long | Batch embed (32 at a time), progress-log, resumable via `nodes_vec` rowid gaps |

**Dependencies:**
- Consumes **R6 centrality** output when R6 is live; falls back to `rank_by_in_degree` otherwise.
- Consumes **R9 annotation quality** indirectly — cleaner summaries → better embeddings. R9 is
  not a hard blocker.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R1)
- Parent roadmap: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
- `sqlite-vec` docs: https://github.com/asg017/sqlite-vec
- `bge-small-en-v1.5` model card: https://huggingface.co/BAAI/bge-small-en-v1.5
- Cormack et al. "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning
  Methods" (SIGIR 2009)

## Handoff

Ready for `kitty:work`. Entry point: Unit 1 (migration + deps). Units 2–5 can be worked in
parallel once Unit 1 lands. Unit 6 is the exit gate — merges only when ≥15% recall@10 improvement
is demonstrated on the in-repo fixture.
