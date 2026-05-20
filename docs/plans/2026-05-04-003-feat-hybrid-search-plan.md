---
title: Hybrid Semantic + Lexical + Graph Search (R1)
type: feat
status: in_progress
date: 2026-05-04
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R1
units:
  - id: 1
    title: Dependency + migration scaffolding
    state: complete
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
| R1.b — Graph-centrality leg fused into ranking | Unit 3 (reads existing `nodes.centrality`) |
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

## Memory Context

Treat-box and litter-box queries (graph DB at `.pawprints/graph.db`, keywords: `embed`, `hybrid`,
`search`, `lsp`, `pyright`, `rrf`, `vec`, `language server`, `reference`, `sqlite`) returned no
topic-specific entries for hybrid retrieval, embeddings, `sqlite-vec`, or RRF as of 2026-05-04.
The treat box currently holds only general process conventions (the plan-state `**State:**`
standalone-paragraph rule and the `AskUserQuestion` skills protocol). The litter box is empty.
No prior failures or anti-patterns constrain this plan. Note that this refresh diverges from
the predecessor on two technical points — the embedding stack (Model2Vec instead of
`sentence-transformers`, motivated by the "least computationally expensive" requirement) and
the centrality channel (consume `nodes.centrality` directly now that R6 is shipped). Record any
embedding-model-load, `sqlite-vec` platform, or RRF tuning lessons during execution so
subsequent refreshes inherit them.

## Context & Research

### Annotation Status

- Total nodes: 946, annotated: 946 (100%), pending: 0, stale: 0.
- 100% annotation coverage means we can back-fill embeddings in a single batch pass.

### Target Files

- `src/cartograph/storage/schema.py` — add embedding virtual-table reference.
- `src/cartograph/storage/migrations/0006_hybrid_search.sql` — **new migration**.
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
- `nodes.centrality` (added by migration `0004_centrality.sql`, R6 — already shipped) holds a
  weighted-PageRank score in `[0, 1]`, refreshed lazily via
  `GraphStore._ensure_centrality_fresh()`. The graph-boost channel reads this column directly;
  no recomputation, no in-degree fallback path needed.

## Key Technical Decisions

### Embedding model: `minishlab/potion-base-8M` via `model2vec` (256-dim, ~32 MB, pure NumPy)

Rationale (chosen for the user's "least computationally expensive" requirement):
- **Zero-PyTorch, zero-ONNX:** `model2vec` depends on `numpy`, `tokenizers`, and `safetensors`
  — no `torch`, no `transformers`. Install footprint is ~50 MB versus ~700 MB–1 GB for
  `sentence-transformers` (which transitively pulls CUDA-bundled torch wheels by default on
  Linux).
- **Static lookup embeddings:** distilled from sentence-transformer models into a
  token-vector lookup + mean-pool. No transformer inference at query time. Encode latency is
  ~0.05–0.5 ms per text on CPU vs. ~5–20 ms for transformer-based encoders. No GPU needed,
  no model-warmup cost.
- **Quality:** retains ~85–90% of `bge-small-en-v1.5` recall on retrieval benchmarks; the gap
  narrows further on short summary text (the regime this plan targets). MTEB scores are
  competitive with `all-MiniLM-L6-v2`.
- **Size:** ~32 MB on disk. Bundled or pulled once on first run.
- **Dimensionality:** 256-d. `sqlite-vec` handles arbitrary dimensions; 256 keeps `nodes_vec`
  rows compact.

v2 candidates if Unit 6 eval shows summary recall is insufficient:
- `fastembed` + `BAAI/bge-small-en-v1.5` (ONNX Runtime, ~150 MB install, ~5 ms encode) — strict
  Pareto improvement on quality vs. install size compared to `sentence-transformers`.
- `model2vec` + `minishlab/potion-base-32M` (512-dim, ~120 MB) — same library, larger distilled
  model.
Both upgrade paths preserve the `Embedder` API; only Unit 1 deps and Unit 2 model name change.

### Fusion algorithm: Reciprocal Rank Fusion with k=60

`score(d) = Σ_c (1 / (k + rank_c(d)))` for each channel c. k=60 is the standard-literature default
(Cormack et al. 2009); no per-channel weight tuning required.

### `sqlite-vec` integration: loaded at connection time

- Add `sqlite-vec` to dependencies in `pyproject.toml`.
- In `cartograph.storage.connection::create_connection`, call `conn.enable_load_extension(True)` and
  `sqlite_vec.load(conn)` once before running migrations. Gracefully disable the dense channel and
  log a warning if load fails (platform fallback).
- Virtual table: `CREATE VIRTUAL TABLE nodes_vec USING vec0(embedding float[256])` keyed by
  `nodes.id`.

### Degraded mode (sqlite-vec unavailable)

- `GraphStore.search` checks a `_vec_available` flag. If false, fuse only FTS5 + centrality. Log
  `"Hybrid search in degraded mode: dense channel disabled (sqlite-vec not loaded)"`. Tests exercise
  both paths.

## Resolved Decisions

- **`search` exposes a `mode` parameter** (`hybrid` | `lexical` | `dense`), default `hybrid`.
  Required by Unit 6 to measure the lexical baseline cleanly; gives agents an opt-out for
  deterministic FTS5 behavior.
- **Held-out query fixtures ship in-repo** under `tests/evaluation/` (~40 queries hand-authored
  against the current graph). Keeps the recall@10 measurement reproducible in CI.

## Open Questions

### Defer

- Code-chunk embeddings vs. summary-only. Measure summary-only first; revisit after Unit 6.
- Eval set augmentation: if hand-authored queries prove insufficient, augment with synthetic
  paraphrastic queries (sample sibling-node summaries, mask the head term) before raising the
  recall@10 target.

## Implementation Units

### Unit 1 — Dependency + migration scaffolding

**State:** complete

- [ ] Add `sqlite-vec>=0.1.1` to `pyproject.toml` dependencies.
- [ ] Add `model2vec>=0.3.0` to `pyproject.toml` dependencies. **Do not add
      `sentence-transformers` or `torch`** — see the embedding-model decision above.
- [ ] Write `src/cartograph/storage/migrations/0006_hybrid_search.sql`:
      `CREATE VIRTUAL TABLE IF NOT EXISTS nodes_vec USING vec0(embedding float[256])`.
- [ ] Update `cartograph.storage.connection::create_connection` to load the `sqlite_vec` extension
      with try/except fallback. Set a `_vec_available` flag (on the connection or alongside the
      GraphStore) so downstream code can branch on it.
- [ ] Add a CI matrix step that imports `sqlite_vec` and calls `sqlite_vec.load(conn)` on the
      project's supported Pythons (3.13, 3.14) on macOS, Linux, and Windows. Capture the
      pass/fail status per matrix cell; do not break the build on a load failure (degraded mode
      is a supported path) but surface failures clearly so we know which platforms run in
      degraded mode by default.

**Files:**
- `pyproject.toml` (modify)
- `src/cartograph/storage/migrations/0006_hybrid_search.sql` (new)
- `src/cartograph/storage/connection.py` (modify)
- `.github/workflows/ci.yml` (or equivalent — add the sqlite-vec smoke step)

**Verification:**
- `uv sync --all-extras` succeeds without pulling `torch`.
- `uv run python -c "import sqlite_vec; import model2vec"` succeeds.
- `uv run python -c "import torch"` **fails** (negative test confirming torch was not pulled in
  transitively).
- `uv run pytest tests/test_storage.py` still green; new test asserts that opening a fresh
  GraphStore creates the `nodes_vec` table when sqlite-vec is available and logs a warning
  otherwise.

**Test scenarios:**
- Happy: `sqlite_vec.load()` succeeds → `_vec_available = True` → `nodes_vec` table exists.
- Error: simulated `load()` failure → `_vec_available = False` → GraphStore still functional;
  the FTS5 + centrality fusion path is exercised in tests.

### Unit 2 — Embedding generator module

**State:** pending

- [ ] Create `src/cartograph/annotation/embeddings.py` exporting:
      - `Embedder.get_instance()` → singleton loading `minishlab/potion-base-8M` lazily via
        `StaticModel.from_pretrained` (`model2vec`'s static-model loader).
      - `Embedder.embed(text: str) -> list[float]` (dim=256).
      - `Embedder.embed_batch(texts: list[str]) -> list[list[float]]`.
- [ ] Model file is loaded on first call, not at import time. Cached under `.pawprints/models/`
      so repeated runs don't re-fetch. Honor a `KITTY_EMBED_MODEL_PATH` env var pointing at a
      pre-downloaded model directory (firewall fallback).
- [ ] Pure-NumPy code path — assert no `torch`, no ONNX, no GPU. Encode latency target: <1 ms
      per text single-threaded on commodity CPU.

**Files:**
- `src/cartograph/annotation/embeddings.py` (new)

**Verification:**
- Unit test with a tiny text corpus confirms vectors are 256-d, normalized, and deterministic.
- Unit test asserts `sys.modules` does **not** contain `torch` after `Embedder.get_instance()`
  returns (negative test guarding against accidental torch re-introduction).

**Test scenarios:**
- Happy: `embed("foo")` returns 256-d list; `embed_batch(["foo", "bar"])` returns 2 vectors.
- Cold start: model file fetched on first call (or loaded from `KITTY_EMBED_MODEL_PATH`);
  second call returns the cached singleton without re-loading.
- Error: model load failure (disk full, no network, no env-var override) raises
  `EmbeddingError`. Callers must treat dense-channel population as best-effort.

### Unit 3 — Graph-centrality channel

**State:** pending

- [ ] Add `GraphStore.centrality_score(node_ids: list[int]) -> dict[int, float]`. Body is a
      single `SELECT id, centrality FROM nodes WHERE id IN (?, ?, ...)` after calling
      `self._ensure_centrality_fresh()`. Returns the cached PageRank score from
      `nodes.centrality` (already normalised to `[0, 1]` by migration `0004_centrality.sql`).
      No re-normalization, no in-degree fallback, no extra caching layer.
- [ ] If a row reports `centrality IS NULL` (only possible inside the lazy-refresh window),
      treat the score as 0 — RRF resolves the tie using the lexical/dense channels.

**Files:**
- `src/cartograph/storage/graph_store.py` (modify; ~10-line method body)

**Verification:**
- Unit test asserts the dict returned matches the values written into `nodes.centrality` after
  `_ensure_centrality_fresh()` runs.
- Unit test asserts the `centrality IS NULL` path returns 0 for the affected node and does not
  raise.

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
      1. For each successfully written annotation, evaluate quality. If the annotation would be
         flagged by `cartograph.annotation.quality.find_low_quality_annotations` (placeholder
         summary, missing-name-reference, generic-fallback role), **skip embedding generation**
         so the dense channel doesn't get polluted with near-duplicate fallback vectors.
      2. Otherwise compute `Embedder.embed(summary + " " + qualified_name)` (combining both
         gives better recall on name-heavy queries).
      3. Upsert into `nodes_vec` via `INSERT OR REPLACE INTO nodes_vec(rowid, embedding) VALUES
         (?, ?)`.
- [ ] Add a one-shot back-fill: `uv run python -m cartograph.annotation.embeddings_backfill`
      iterates over all annotated, embedding-eligible nodes missing a vector and fills them.
      Idempotent. Reports a breakdown of (filled, skipped-low-quality, errored) counts so the
      eval harness can sanity-check coverage before running recall@10.
- [ ] On model load or embed failure inside `write_annotations`, log a single warning per
      process, persist the annotation without an embedding, and continue. Embedding gaps are
      recoverable on the next back-fill run.

**Files:**
- `src/cartograph/annotation/annotator.py` (modify)
- `src/cartograph/annotation/embeddings_backfill.py` (new)

**Test scenarios:**
- Happy: annotating a high-quality node writes both `summary` and a matching row in
  `nodes_vec`.
- Happy: annotating a low-quality node (per `find_low_quality_annotations`) writes `summary`
  only; no row in `nodes_vec`. The node is still findable via FTS5 + centrality.
- Happy: back-fill on the existing 946-annotated DB produces N≤946 vectors (skipping any
  flagged low-quality nodes) and reports the breakdown.
- Error: if `Embedder.embed` fails, annotation persistence still succeeds; a warning log is
  emitted; the node remains eligible for back-fill on the next run.

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
- **Graph DB size:** ~1 KB per node at 256-d float32 (~970 KB total for 946 nodes; ~1.0 MB per
  1000 nodes). Row per node in `nodes_vec`. Excludes any low-quality nodes that skip embedding
  per Unit 5.
- **First-run latency:** static model file fetch (~32 MB) on first annotation or first search,
  cached under `.pawprints/models/`. No PyTorch import (~0 ms vs. ~1–2 s for
  `sentence-transformers`); no transformer warmup; no GPU initialization path.
- **Per-query latency:** FTS5 ~5 ms + dense encode ~0.5 ms (Model2Vec lookup + mean-pool)
  + dense `vec0` search ~5 ms (256-d over ~1k vectors) + centrality lookup ~2 ms + fusion
  ~1 ms ≈ ~14 ms p50. Comfortably under the existing 100 ms test assertion, and roughly half
  the latency of the sentence-transformers alternative.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| `sqlite-vec` extension load disabled in the user's Python build (common on some macOS Homebrew Python releases) | Degraded mode disables dense channel; Unit 1 CI matrix verifies the load on supported Pythons; document `pysqlite3-binary` shim in Unit 7 if any matrix cell fails. |
| Model file fetch fails behind a firewall | `KITTY_EMBED_MODEL_PATH` env var points at a pre-downloaded directory; documented in Unit 7. |
| RRF tuning produces regressions vs. pure FTS5 on very short/exact queries | `mode="lexical"` escape hatch; Unit 6 measures recall@1 specifically. |
| Static-embedding quality insufficient on paraphrastic queries | Unit 6 is the gate. If recall@10 misses the +15% target, the v2 fallback is `fastembed` + `BAAI/bge-small-en-v1.5` (ONNX, no torch). The `Embedder` interface absorbs the swap; Unit 1 deps and Unit 2 model name are the only file-level changes. |
| Back-fill on a huge repo takes too long | Per-text encode is ~ms-class; batch and progress-log; resumable via `nodes_vec` rowid gaps. |
| Low-quality annotations pollute the dense channel | Unit 5 skips embedding for nodes flagged by `find_low_quality_annotations`. |

**Dependencies:**
- Consumes the existing `nodes.centrality` column from `0004_centrality.sql` (R6 — **shipped**).
  No fallback path needed; Unit 3 reads the column directly.
- Consumes **R9 annotation quality** as a hard input (not "indirectly"): Unit 5 calls into
  `cartograph.annotation.quality.find_low_quality_annotations` to decide whether a node is
  embedding-eligible. R9's quality functions must be importable and its thresholds
  production-ready before Unit 5 merges.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R1)
- Predecessor plan (refresh source): `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md`
- `sqlite-vec` docs: https://github.com/asg017/sqlite-vec
- `model2vec` library: https://github.com/MinishLab/model2vec
- `minishlab/potion-base-8M` model card: https://huggingface.co/minishlab/potion-base-8M
- Cormack et al. "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning
  Methods" (SIGIR 2009)

## Handoff

Ready for `kitty:work`. Entry point: Unit 1 (migration + deps). Units 2–5 can be worked in
parallel once Unit 1 lands. Unit 6 is the exit gate — merges only when ≥15% recall@10 improvement
is demonstrated on the in-repo fixture.
