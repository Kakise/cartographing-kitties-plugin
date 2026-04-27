---
title: Plugin Evolution Roadmap (R1–R9)
type: feat
status: active
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
plans:
  - docs/plans/2026-04-23-002-feat-hybrid-search-plan.md
  - docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md
  - docs/plans/2026-04-23-004-feat-language-expansion-plan.md
  - docs/plans/2026-04-23-005-feat-commit-history-plan.md
  - docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md
  - docs/plans/2026-04-23-007-feat-centrality-surface-plan.md
  - docs/plans/2026-04-23-008-feat-watch-mode-plan.md
  - docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md
  - docs/plans/2026-04-23-010-feat-annotation-quality-plan.md
---

# Plugin Evolution Roadmap — R1–R9

## Overview

This is the meta-plan for the 2026 Cartographing Kittens evolution brainstorm. Each requirement
R1–R9 from the brainstorm gets its own per-requirement plan (linked above). This document
sequences them, captures cross-cutting decisions, and names the gates that determine when each
requirement is ready to pick up.

**Guiding principles (inherited from the brainstorm):**

1. **SQLite stays.** No new service dependency. `sqlite-vec` for vectors, `git log` for history,
   `coverage.py` JSON for tests — all local.
2. **Tree-sitter stays primary.** LSP and embeddings are additive, not replacements.
3. **Inline-first contract preserved.** Every new capability must work without swarm orchestration.
4. **Codex manifest contract preserved.** No changes that force Codex out of inline execution.

## Problem Frame

The brainstorm established three 2026 gaps the current plugin does not close:

1. Hybrid retrieval is the norm — Cartograph is lexical + graph, missing dense.
2. LSP is an agent primitive — Cartograph derives references heuristically from the AST.
3. Graphs are multi-dimensional — Cartograph is structure-only; no history, no coverage, no team signals.

The roadmap breaks these gaps into nine self-contained requirements. Each R produces a coherent plan
that `kitty:work` can execute without pulling in others, but the order matters: some R produce the
infrastructure later R reuse (schema columns, fusion surface, tool scaffolding).

## Requirements Trace

Each requirement maps to exactly one plan. Tier comes from the brainstorm.

| R | Title | Tier | Plan |
|---|---|---|---|
| R1 | Hybrid semantic + lexical + graph search | 1 | `2026-04-23-002-feat-hybrid-search-plan.md` |
| R2 | LSP bridge for semantic precision | 1 | `2026-04-23-003-feat-lsp-bridge-plan.md` |
| R3 | Expanded language coverage (Go, Rust, Java) | 1 | `2026-04-23-004-feat-language-expansion-plan.md` |
| R4 | Commit-history dimension | 2 | `2026-04-23-005-feat-commit-history-plan.md` |
| R5 | Test-coverage edges | 2 | `2026-04-23-006-feat-test-coverage-edges-plan.md` |
| R6 | Centrality & re-ranking surface | 2 | `2026-04-23-007-feat-centrality-surface-plan.md` |
| R7 | Watch mode / live graph subscription | 3 | `2026-04-23-008-feat-watch-mode-plan.md` |
| R8 | Shared / remote graph cache | 3 | `2026-04-23-009-feat-shared-graph-cache-plan.md` |
| R9 | Annotation quality gates & acceleration | 3 | `2026-04-23-010-feat-annotation-quality-plan.md` |

## Scope Boundaries

- **In scope:** ordering, cross-cutting decisions, shared primitives, migration numbering, and gates.
- **Out of scope:** per-requirement implementation detail (lives in each linked plan), R10–R14
  (explicitly deferred by the brainstorm), and any change that would rewrite the SQLite substrate.

## Context & Research

### Annotation Status

- Total nodes: 946
- Annotated: 946 (100%)
- Pending: 0, Stale: 0

### Ground-Truth Extension Points (verified against live graph)

- **`src/cartograph/storage/schema.py`** — schema reference. Current node-kind CHECK:
  `function, class, method, interface, type_alias, enum, module, file`. Edge-kind CHECK:
  `imports, calls, inherits, contains, depends_on`. `nodes_fts` virtual table over
  `name, qualified_name, summary`.
- **`src/cartograph/storage/migrations/`** — `0001_baseline.sql`, `0002_graph_reactive.sql`. Next free
  numbers: `0003_*` onward. Each R that touches schema reserves one migration number below.
- **`src/cartograph/storage/graph_store.py`** — `GraphStore` class (lines 21–908). Already exposes
  `rank_by_in_degree`, `rank_by_transitive`, `compute_diff`, `snapshot_nodes`, `snapshot_edges`.
  R6 inherits these; R7 builds on `compute_diff`.
- **`src/cartograph/parsing/extractors.py`** — Python and TS/JS extractors via `_extract_python_*` /
  `_extract_ts_*` functions dispatched by `extract_definitions`, `extract_imports`, `extract_calls`.
  R3 adds `_extract_go_*`, `_extract_rust_*`, `_extract_java_*` triplets.
- **`src/cartograph/parsing/queries.py`** — per-language tree-sitter node-type sets. R3 adds entries.
- **`src/cartograph/parsing/registry.py`** — `ParserRegistry` with `_get_language`. R3 adds grammars.
- **`src/cartograph/server/tools/query.py`** — `search`, `query_node`, `batch_query_nodes`,
  `get_context_summary`, `get_file_structure`. R1 extends `search`; R6 extends `get_context_summary`.
- **`src/cartograph/server/tools/reactive.py`** — `graph_diff`, `validate_graph`. R7 extends with
  `subscribe_graph_changes`.
- **`src/cartograph/server/tools/annotate.py`** — `get_pending_annotations`, `submit_annotations`,
  `find_stale_annotations`. R9 extends quality gating here.
- **`src/cartograph/annotation/annotator.py`** — `NodeContext`, `get_pending_nodes`,
  `write_annotations`, `extract_source`. R9 modifies quality checks; R1 hooks in to write embeddings
  at annotation time.
- **`src/cartograph/memory/memory_store.py`** — separate SQLite file for litter/treat boxes. R4 may
  write commit-message derived memories here.
- **`src/cartograph/indexing/indexer.py`** — `Indexer::index_all`, `Indexer::index_changed`. R4 hooks
  in during indexing to capture git metadata; R3 touches extractor dispatch.
- **`src/cartograph/indexing/discovery.py`** — `detect_changes` already uses git-diff first,
  hash-fallback second. R7 replaces the trigger (wall-clock) with filesystem watcher.

### Current Tool Surface (for impact analysis)

Total MCP tools: 13 (per `CLAUDE.md`). After R1–R9 the surface becomes:

| New tool | Source R | Module |
|---|---|---|
| (none — `search` is extended in-place) | R1 | `query.py` |
| `find_references`, `goto_definition`, `get_type`, `get_diagnostics` | R2 | `tools/lsp.py` (new) |
| `find_co_changed`, `get_change_history` | R4 | `tools/history.py` (new) |
| `find_tests_for` | R5 | `tools/coverage.py` (new) |
| `subscribe_graph_changes` | R7 | `reactive.py` (extended) |
| `publish_graph`, `pull_graph` | R8 | `tools/sharing.py` (new) |

Final surface: **13 + 9 = 22 tools**.

## Key Technical Decisions

### Sequencing

Ordered by **leverage × unblocking × cost**, respecting the brainstorm's "hybrid before LSP" and
"R4 over R5" calls:

**Phase α — Retrieval foundation (weeks 1–3):**
1. **R6 (centrality surface)** — cheapest, touches only re-ranking. Ships in days. Becomes the
   graph-boost channel that R1 fuses in step 3.
2. **R9 (annotation quality)** — runs cheap auto-detection over the 946 existing nodes and
   re-queues placeholders. Raises the summary quality that R1's dense embeddings will consume.
3. **R1 (hybrid search)** — the headline win. Consumes R6's centrality output as the graph channel
   of the RRF fusion and R9's cleaned summaries as the dense-embedding corpus.

**Phase β — Differentiation (weeks 4–5):**
4. **R4 (commit history)** — unique positioning per the brainstorm's "Key Decisions". Schema
   additions are additive; depends on nothing from phase α.

**Phase γ — Polyglot (weeks 6–9):**
5. **R3 (language expansion)** — Go, Rust, Java via tree-sitter. Each language ships independently.
   Recommended order: Go → Java → Rust (Go is the simplest extractor; Rust has the richest traits).
6. **R5 (test-coverage edges)** — partially depends on R3 for multi-language test detection
   (pytest, go test, jest, junit). Heuristic pass can ship per-language as R3 lands.

**Phase δ — Precision (weeks 10–13):**
7. **R2 (LSP bridge)** — highest-effort item (lifecycle, per-language server bootstrap). Deliberately
   last in the retrieval-precision track because RRF from R1 already handles most cases.

**Phase ε — DX (parallel any time after α):**
8. **R7 (watch mode)** — can ship in parallel with γ or δ. Only depends on existing `graph_diff`.
9. **R8 (shared cache)** — parallel with γ or δ. Only depends on the SQLite file being portable.

### Cross-Cutting Decisions

- **Migration numbering reserved up front:**
  - `0003_hybrid_search.sql` — R1 (nodes_embeddings virtual table via sqlite-vec)
  - `0004_centrality.sql` — R6 (centrality cache columns)
  - `0005_commit_history.sql` — R4 (last_touched_at, change_frequency, new edge kinds)
  - `0006_test_coverage.sql` — R5 (tests edge kind; no node-kind changes)
  - `0007_lsp_provenance.sql` — R2 (edge properties: verified_by_lsp flag)
  - No migration needed for R3 (node kinds cover all target languages), R7, R8, R9.

- **Edge-kind extensions** (all via migrations relaxing the CHECK constraint):
  - R4 introduces `authored_by`, `co_changed_with`.
  - R5 introduces `tests`.
  - R2 does not introduce new edge kinds but adds `verified_by_lsp` to the existing edges'
    `properties` JSON.

- **Node-kind extensions:**
  - R3 does **not** add new kinds. Go structs/interfaces, Rust structs/enums/traits, and Java
    interfaces/classes all map to existing kinds (`class`, `interface`, `enum`, `type_alias`,
    `function`, `method`, `module`, `file`).
  - Confirmed via Rust `trait` → `interface`, Go `struct` → `class`, Java mapping is direct.

- **Tool module layout** — new tool modules go under `src/cartograph/server/tools/` alongside the
  existing ones (`query.py`, `analysis.py`, `annotate.py`, `reactive.py`, `memory.py`, `index.py`).

- **Embedding choice for R1 is the one open cross-plan decision.** The per-R1 plan captures the
  choice as an explicit resolution; all other plans are neutral on it.

- **No new service dependency** — any R that tries to introduce one fails review. Ships only if
  degraded mode (without the optional accelerator) works out of the box.

## Open Questions

Only cross-cutting questions live here. Per-R questions live in each linked plan.

### Resolve Before Planning

- **Embedding model choice for R1.** Decision lives in the R1 plan; blocks only R1.
- **LSP lifecycle ownership for R2.** Decision lives in the R2 plan; blocks only R2.
- **R3 v1 language scope.** Decision lives in the R3 plan; recommend **Go first** (smallest
  extractor surface, clearest test bed), then Java, then Rust.

### Deferred (decide once dependencies land)

- **Dense embeddings on code chunks vs. summaries only.** Defer until R1 baseline is measured.
- **R7 as Cartograph concern or harness hook.** Defer until R1 and R4 ship — by then the value of
  live subscription is clearer.
- **R8 as artifact vs. service.** Defer until team-scale usage evidence exists.

## Implementation Units

The roadmap itself has no implementation units — each R is a plan. The roadmap's work is
**sequencing and gate enforcement**. Gates between phases:

- [ ] **Gate α→β:** R1 ships with baseline metrics (recall@10 improvement ≥15% over FTS5-only).
- [ ] **Gate β→γ:** R4 ships with incremental git-log indexing proven on this repo's own history.
- [ ] **Gate γ→δ:** R3 ships Go extractor; R5 ships pytest heuristic; at least one non-Python
      language end-to-end query works.
- [ ] **Gate δ done:** R2 ships `get_diagnostics` post-edit loop verified on this repo.
- [ ] **Gate ε done:** R7 and R8 ship and are documented in README.

## System-Wide Impact

- **Plugin surface grows by 9 MCP tools** (13 → 22). Agent prompts and skill docs update per-R.
- **Graph DB schema grows by 4 migrations** (through 0006; plus 0007 for R2 provenance).
- **Coverage ceiling lifts** from 3 languages to 6 once R3 ships (Python, TS, JS, Go, Rust, Java).
- **Annotation worker load increases** under R1 (embeddings) and R9 (requeued placeholders). R1's
  embedding generation runs once per node and is incremental via `annotated_content_hash`.
- **No backwards-incompatible changes.** All new schema columns nullable; all new edge kinds
  additive; all new tools optional.

## Risks & Dependencies

| Risk | Mitigation | Owning R |
|---|---|---|
| `sqlite-vec` install fragility on some platforms | Ship pure-Python fallback that disables dense channel and logs a warning | R1 |
| LSP server startup time dominates query latency | Lazy spawn + warm-up cache; `get_diagnostics` is on-demand | R2 |
| Go/Rust/Java grammars have breaking releases | Pin tree-sitter grammar versions in `pyproject.toml`; smoke-test in CI | R3 |
| Commit history bloats the graph on large monorepos | Cap `co_changed_with` edges per node; prune edges older than N commits | R4 |
| Coverage JSON parsing is ecosystem-specific | Start with heuristic-only; coverage-JSON parsing is a second pass per language | R5 |
| Centrality computation is O(N²) worst case | Compute lazily on `graph_version` bump; cache in a column | R6 |
| Filesystem watcher fires on every IDE save and thrashes indexing | Debounce 500ms; coalesce bursts | R7 |
| Shared graph diverges from live code | Include `graph_version` + git commit hash in the artifact; agents verify before use | R8 |
| Low-quality summary detection false-positives re-queue good nodes | Conservative thresholds; dry-run mode first | R9 |

**External dependencies added across the roadmap:**

- R1: `sqlite-vec` (≥0.1.0), a local embedding model (see R1 plan for the pick).
- R2: `pygls` (≥1.1.0) or direct `subprocess` stdio. Decision in R2 plan.
- R3: `tree-sitter-go`, `tree-sitter-rust`, `tree-sitter-java` (all ≥0.20.0).
- R7: `watchdog` (≥4.0.0) for filesystem events.
- R8: no new dependencies (stdlib `urllib` + existing SQLite file).
- R9: no new dependencies.

All dependencies go into `pyproject.toml` under the relevant extras group so base install stays thin.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md`
- Architecture contract: `docs/architecture/codex-workflow-contract.md`
- Repo boundaries: `docs/architecture/repo-boundaries.md`
- Prior related plan: `docs/plans/2026-04-21-002-refactor-codex-plugin-alignment-plan.md`
- Prior related plan: `docs/plans/2026-03-28-006-feat-graph-reactive-engineering-plan.md`

## Handoff

Each linked plan is ready for `kitty:work` in isolation. Recommended execution order follows
**Sequencing** above. At any time the user may pick a single R and skip the rest.
