---
title: Centrality & Re-Ranking Surface (R6)
type: feat
status: active
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
parent: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
requirement: R6
---

# Centrality Surface — Implementation Plan (R6)

## Overview

Expose PageRank-style centrality and in/out-degree as queryable node fields, computed lazily on
graph-version change and cached. Used to (a) re-rank `search` ties (fuses into R1's graph
channel) and (b) prune `get_context_summary` output to the top-K most central nodes when a file
is large, preventing context blowout. Smallest plan in the roadmap; ships in days.

## Problem Frame

`GraphStore` already has `rank_by_in_degree` and `rank_by_transitive`, but these recompute on
every call and their results aren't materialized for join-friendly queries. `get_context_summary`
currently returns nodes ordered by direct in-degree — usable but non-normalized and not mixable
with R1's RRF fusion. The goal is to cache a per-node centrality score, keep it fresh via the
existing `graph_version` counter, and expose it wherever ranking or pruning matters.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R6.a — Cached `centrality` and `in_degree_cache` columns on `nodes` | Unit 1 |
| R6.b — Lazy recompute on `graph_version` bump | Unit 2 |
| R6.c — PageRank-style centrality (normalized 0–1) | Unit 2 |
| R6.d — `get_context_summary` prunes to top-K when file exceeds threshold | Unit 3 |
| R6.e — `search` (R1) consumes centrality as its graph channel | Unit 4 (R1 integration) |

## Scope Boundaries

- **In scope:** schema additions, PageRank computation, cache invalidation, `get_context_summary`
  behavior change, a small seam for R1 consumption.
- **Out of scope:** per-scope centrality (e.g., centrality within a single module — doable with
  existing `scope` param on `rank_nodes` but not cached); betweenness / closeness centrality
  (PageRank covers the use cases).

## Context & Research

### Extension Points

- `src/cartograph/storage/schema.py` — nodes table needs `centrality REAL` and
  `in_degree_cache INTEGER` columns.
- `src/cartograph/storage/migrations/0004_centrality.sql` — new migration.
- `src/cartograph/storage/graph_store.py`:
  - `rank_by_in_degree` (lines visible in context) already computes in-degree inline — now reads
    `in_degree_cache` directly when `graph_version` matches.
  - New `compute_centrality()` method.
  - `increment_graph_version()` triggers a deferred recompute flag.
- `src/cartograph/server/tools/query.py::get_context_summary` — adds top-K pruning path.

### Algorithm Choice: Weighted PageRank

- Edges weighted by kind: `calls` = 1.0, `imports` = 0.6, `inherits` = 0.9, `contains` = 0.3,
  `depends_on` = 0.5. Reflects semantic weight of different relationships; `contains` is lowest
  because every file contains its children trivially.
- Damping factor 0.85 (canonical).
- Iterations: 50 (converges well below for graphs <10K nodes; empirical).
- Normalize to [0, 1] by dividing by the max score after convergence.

### Recompute Trigger

- `increment_graph_version()` currently bumps `graph_meta.graph_version`.
- Add a sentinel column `graph_meta.centrality_version`. Centrality is "stale" when
  `centrality_version < graph_version`.
- Recompute on first read access after stale (lazy), not eagerly on each bump (avoids thrashing
  during bulk insert).
- Compute runs as a 50-iteration Python loop over rows fetched from SQLite. The plan originally
  reserved an iterative-CTE option, but the implementation chose pure Python for clarity, easier
  unit testing, and trivial dangling-mass redistribution. Persistence is still a batched
  `executemany` UPDATE. ~50 lines of Python plus the cache-stamping logic.

## Open Questions

### Resolve Before Implementing

- **Is 50 iterations always enough?** For graphs <10K nodes, yes. For 10K–100K nodes, verify by
  measuring L1 delta between iterations. Recommend: cap at 50, log a warning if final delta >
  0.01.
- **Should centrality be re-exposed as an MCP tool (`node_centrality`)?** Recommend: no — expose
  via the existing `rank_nodes` and `query_node` responses (already returns `in_degree`; add
  `centrality`). Avoids tool surface bloat.

### Defer

- Scope-restricted cached centrality (centrality within a module). Currently on-the-fly via
  `rank_nodes(scope=...)` is fine.

## Implementation Units

### Unit 1 — Schema + migration

- [ ] `src/cartograph/storage/migrations/0004_centrality.sql`:
      - `ALTER TABLE nodes ADD COLUMN centrality REAL`
      - `ALTER TABLE nodes ADD COLUMN in_degree_cache INTEGER`
      - `ALTER TABLE graph_meta ADD COLUMN centrality_version INTEGER DEFAULT 0`
      - Index: `CREATE INDEX idx_nodes_centrality ON nodes(centrality DESC)`.

**Verification:** migration runs cleanly; existing rows show NULL centrality and are recomputed
on next read.

### Unit 2 — Compute + cache

- [x] `GraphStore.compute_centrality()`:
      1. Cache-freshness check lives in `_ensure_centrality_fresh`: returns early when
         `centrality_version >= graph_version` AND no node has `centrality IS NULL`.
      2. Fetch all nodes and edges, accumulate in-degree and outgoing edge weights in Python.
      3. Run a 50-iteration weighted PageRank loop in Python with damping=0.85, dangling mass
         redistributed uniformly, early stop at L1 delta < 1e-8, warning when final delta > 0.01.
      4. Persist results: `executemany` of
         `UPDATE nodes SET centrality = ?, in_degree_cache = ? WHERE id = ?`.
      5. `UPDATE graph_meta SET centrality_version = graph_version`.
- [ ] Wrap in a read-before-write guard: any method that needs centrality calls
      `_ensure_centrality_fresh()` first.
- [ ] Methods that consume: `rank_by_in_degree`, `rank_by_transitive`, `context_summary`,
      `search` (R1).

**Test scenarios:**
- Happy: bulk insert 1K nodes/5K edges; first `rank_by_in_degree` call triggers compute; second
  call uses cache (asserts via time delta or mocked compute counter).
- Edge: an edge upsert triggers `graph_version` bump — next centrality read recomputes.
- Edge: graph with 0 edges → all centrality values 1/N.

### Unit 3 — `get_context_summary` pruning

- [ ] In `query.py::get_context_summary`, if the resolved node list for any single file exceeds
      `max_nodes` (existing param, default 50), **select the top-K by centrality** rather than by
      raw in-degree.
- [ ] If R1 hasn't landed yet, `centrality` being NULL falls back to the existing in-degree
      ordering. Graceful degradation.

**Test scenarios:**
- Happy: file with 80 nodes, `max_nodes=50` → returns the 50 highest-centrality nodes.
- Edge: file with fewer nodes than cap → returns all, unchanged.
- Edge: centrality NULL for all (fresh DB pre-compute) → falls back to in-degree ordering; no
  crash.

### Unit 4 — Expose on query responses

- [ ] `query_node`, `batch_query_nodes`, `get_context_summary`, `rank_nodes`, and
      `get_file_structure` response payloads gain a `centrality: float` field on each node dict.
- [ ] `_summarise_node` updated once in `query.py`; all tools benefit.
- [ ] R1's `search` fusion consumes `centrality` directly — no separate lookup needed. This plan
      pre-wires the field; R1 plan specifies the fusion math.

**Files:** `src/cartograph/server/tools/query.py::_summarise_node` (modify).

### Unit 5 — Tests

- [ ] `tests/test_centrality.py`:
  - Small known-graph PageRank ground truth (e.g., classic 4-node Wikipedia example) — assert
    our implementation matches expected to 3 decimal places.
  - Cache hit/miss behavior via graph-version bumps.
  - Weighted PageRank: a node with many `calls` edges ranks above one with the same count of
    `contains` edges.

### Unit 6 — Documentation

- [ ] Update `CLAUDE.md` to mention that `query_node` / `search` / `rank_nodes` responses include
      `centrality`.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md` to document the field.

## System-Wide Impact

- **Plugin surface:** no new tools; existing tools gain a `centrality` field.
- **Schema:** +2 columns on `nodes`, +1 column on `graph_meta`.
- **Query latency:** first read after a graph-version bump recomputes (≈100 ms for this repo's
  946 nodes). Subsequent reads read the cache (µs). Bulk indexing bumps `graph_version` once per
  index run, so the recompute hits once per index, not once per insert.
- **Agent behavior:** `expert-kitten-impact` can use `centrality` to prioritize findings.
  `librarian-kitten-researcher` can return the most central symbols first. Neither change is
  strictly required by this plan — documented as "available" in the skill docs.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| PageRank compute slow on very large graphs | Cap iterations; log timing; fall back to in-degree if compute takes > 2 s |
| Edge-kind weights are opinionated and may not generalize | Centralize weights in a constant; document; easy to tune |
| Cache invalidation missed for some write path | `increment_graph_version()` is the single bump point; all writes already call it |

**Dependencies:** none. Prerequisite for **R1** (hybrid search) to use centrality as its graph
channel, but R1 has a fallback to `rank_by_in_degree` if R6 isn't yet shipped.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R6)
- Parent roadmap: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
- PageRank: Page et al. 1998. Standard iterative formulation.

## Handoff

Ready for `kitty:work`. Smallest plan — target 1–2 days. Entry point: Unit 1. Units 2–4
sequential. Unit 5 (tests) runs throughout.
