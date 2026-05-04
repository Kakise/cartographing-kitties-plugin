---
title: Commit-History Dimension (R4)
type: feat
status: active
date: 2026-05-04
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R4
units:
  - id: 1
    title: Migration + schema changes
    state: pending
  - id: 2
    title: Git log parser
    state: pending
  - id: 3
    title: Co-change computation
    state: pending
  - id: 4
    title: Indexer integration
    state: pending
  - id: 5
    title: MCP tools
    state: pending
  - id: 6
    title: Commit-message → memory entries (optional)
    state: pending
  - id: 7
    title: Documentation
    state: pending
---

# Commit-History Dimension — Implementation Plan (R4)

## Overview

Fold git commit history into the Cartograph graph so agents can reason about *when* and *with
what* code has changed — the brainstorm's named differentiator. Adds two new edge kinds
(`authored_by`, `co_changed_with`), two per-node fields (`last_touched_at`, `change_frequency`),
and two MCP tools (`find_co_changed`, `get_change_history`). Incremental per run via `git log`
since the last indexed commit.

## Problem Frame

Structural graphs are commoditized in 2026. The brainstorm's "Key Decisions" identifies
commit-history + memory (litter/treat) as Cartograph's defensible position. Agents today cannot
answer *"what functions usually change with this one?"* — a signal reviewers use every day. R4
captures that signal.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R4.a — `authored_by` edges (node → author pseudo-node) | Unit 2 |
| R4.b — `co_changed_with` edges (function ↔ function) | Unit 3 |
| R4.c — `last_touched_at`, `change_frequency` node fields | Unit 2 |
| R4.d — Incremental update using `git log` since last index | Unit 4 |
| R4.e — `find_co_changed` and `get_change_history` MCP tools | Unit 5 |
| R4.f — Commit-message derived litter/treat-box entries | Unit 6 (opt-in) |

## Scope Boundaries

- **In scope:** git-log parsing, new edge kinds, per-node metadata, co-change computation and
  pruning, two new MCP tools, optional commit-message heuristics for memory entries.
- **Out of scope:** blame-line-level attribution (too expensive for large files); merge-commit
  handling beyond first-parent; GitHub PR / review data; non-git VCS support.

## Memory Context

No relevant memory entries found.

## Context & Research

### Extension Points

- `src/cartograph/storage/schema.py` — edge-kind CHECK currently:
  `('imports', 'calls', 'inherits', 'contains', 'depends_on')`. Must be extended.
- `src/cartograph/storage/migrations/0005_commit_history.sql` — **new migration**:
  - `ALTER TABLE nodes ADD COLUMN last_touched_at TEXT`
  - `ALTER TABLE nodes ADD COLUMN change_frequency INTEGER DEFAULT 0`
  - Drop and re-create the edges CHECK constraint (SQLite: rename-recreate-copy pattern).
- `src/cartograph/indexing/indexer.py` — new pass in `index_all` and `index_changed` after node
  upserts.
- `src/cartograph/indexing/history.py` — **new module**: git-log parsing + co-change computation.
- `src/cartograph/server/tools/history.py` — **new**: two MCP tools.
- `src/cartograph/storage/graph_store.py` — new helpers for reading/writing history fields and
  storing an `indexed_commit_sha` in `graph_meta`.

### Author Nodes

Authors are first-class nodes with `kind='module'` and `qualified_name = 'author::<email>'`,
so existing query tools find them without new kinds. Rationale: avoids a fifth node-kind
relaxation and keeps the author pseudo-symbol queryable via `rank_nodes` (high-authorship authors
become visible structural hubs).

### Co-Change Definition

Two symbols A and B have a `co_changed_with` edge if they were modified in the same commit
(excluding merge commits) ≥ N times within the last M commits. Default N=3, M=500. Stored
weight = count of co-changes.

## Key Technical Decisions

### Incremental git log from stored commit SHA

Store `indexed_commit_sha` in `graph_meta`. On each `Indexer.index_all` / `index_changed`:

1. Read `indexed_commit_sha`.
2. Run `git log --pretty=%H%x09%ae%x09%at --name-only <sha>..HEAD` (tab-separated format).
3. Parse commits into `[{sha, author_email, timestamp, files: [...]}]`.
4. Update `last_touched_at` and increment `change_frequency` per file's owning nodes.
5. Update `authored_by` edges.
6. Recompute `co_changed_with` incrementally by adding this batch's co-change counts.
7. Write new `indexed_commit_sha = HEAD`.

First run (no stored SHA): walk the last M=500 commits and seed.

### File-to-node attribution

Git tracks changes at file granularity; our nodes are sub-file. Attribution rule:
- If a file was modified, attribute the change to the *file-level node* and its direct
  `contains`-children (i.e., the classes/functions defined in that file).
- Do **not** attribute transitively to nested methods — a whole-file rewrite does not mean every
  method changed. For finer-grained attribution, R2 (LSP) could help in v2; out of scope here.

### Co-change edge pruning

Without pruning, `co_changed_with` explodes on large repos. Hard caps:
- Per-node cap: top-K co-changed neighbors by weight (K=30 default).
- Minimum threshold: weight ≥ 3 (don't record one-off coincidences).
- Global cap: `co_changed_with` edges ≤ `nodes_count × 30`.

Pruning runs at the end of each incremental update.

### Author privacy

Author email is recorded as-is from `git log`. Plugin documentation must note this; users with
public graphs should `git config user.email` to a privacy-preserving address or opt out via a
`KITTY_HISTORY_ENABLED=false` environment variable that skips this whole subsystem at index time.

## Open Questions

### Resolve Before Implementing

- **Opt-in or opt-out?** Recommend: opt-in via `KITTY_HISTORY_ENABLED=true` for v1. Reason:
  author-email storage crosses a subtle privacy line. Revisit after shipping; flip default to
  on if feedback is positive.
- **Merge-commit policy.** Use `--no-merges` to skip them entirely. Aligns with co-change semantic
  (merges aren't real co-changes).

### Defer

- Sub-file attribution via line-blame + AST range mapping. Expensive; likely needs R2.
- Per-file decay (old co-changes fade). Simpler: cap by recency window M=500 only.

## Implementation Units

### Unit 1 — Migration + schema changes

**State:** pending

- [ ] Write `src/cartograph/storage/migrations/0005_commit_history.sql`:
      - Add columns `last_touched_at TEXT`, `change_frequency INTEGER DEFAULT 0` to `nodes`.
      - Recreate `edges` table with CHECK constraint extended:
        `kind IN ('imports','calls','inherits','contains','depends_on','authored_by','co_changed_with')`.
      - Add `indexed_commit_sha TEXT` column to `graph_meta`.
- [ ] Add index: `CREATE INDEX idx_nodes_last_touched ON nodes(last_touched_at)`.
- [ ] Update `schema.py`'s documentation string to match.

**Verification:**
- `uv run pytest tests/test_storage.py` green after adding a test that asserts the new columns
  and edge kinds are accepted.

**Test scenarios:**
- Happy: insert an `authored_by` edge — succeeds.
- Edge: fresh DB upgraded from 0004 preserves existing nodes and gains new columns as NULL.

### Unit 2 — Git log parser

**State:** pending

- [ ] `src/cartograph/indexing/history.py::CommitParser` — wraps `subprocess` call to `git log`,
      parses TSV output, yields `Commit` dataclasses (`sha, author_email, timestamp, files`).
- [ ] Handles no-git, detached-HEAD, and empty-repo cases gracefully (yields no commits,
      returns a warning).
- [ ] `update_history(graph_store, repo_root) -> HistoryStats`:
      1. Reads `indexed_commit_sha`.
      2. Determines log range (`<sha>..HEAD` or last 500 commits).
      3. For each commit: updates `last_touched_at`, `change_frequency`, upserts author pseudo-node,
         adds `authored_by` edges.
      4. Collects file-change pairs for Unit 3.
      5. Writes new `indexed_commit_sha` to `graph_meta`.

**Files:** `src/cartograph/indexing/history.py` (new),
`src/cartograph/storage/graph_store.py` (add `set_indexed_commit_sha` / `get_indexed_commit_sha`).

**Test scenarios:**
- Happy: fixture git repo with 5 commits → correct `change_frequency` per file-node.
- Edge: file deleted in a commit — does not crash; does not create a dangling edge.
- Edge: first-run seeding from an empty graph takes the last 500 commits.
- Edge: `KITTY_HISTORY_ENABLED=false` → `update_history` returns immediately with stats
  showing 0 commits processed.

### Unit 3 — Co-change computation

**State:** pending

- [ ] In `history.py`, add `compute_co_changes(commits: Iterable[Commit], store: GraphStore,
      top_k=30, min_weight=3) -> int` which:
      1. For each commit, takes all modified file-level nodes, produces pairs (n choose 2).
      2. Increments an in-memory counter dict `{(a_id, b_id): count}`.
      3. Merges with existing `co_changed_with` edge weights in the store.
      4. Enforces `top_k` per node and `min_weight` threshold — deletes edges below threshold or
         outside the per-node top-K.
      5. Upserts surviving edges with `weight = count`.

**Test scenarios:**
- Happy: two files modified together in 5 commits → `co_changed_with` edge with weight 5.
- Edge: single commit co-changing 10 files produces `C(10,2)=45` pairs, each weight 1 — all
  pruned by `min_weight=3`.
- Edge: top-K pruning keeps highest-weight K neighbors per node.

### Unit 4 — Indexer integration

**State:** pending

- [ ] In `indexing/indexer.py::Indexer.index_all` and `Indexer.index_changed`, call
      `history.update_history(self._store, self._repo_root)` after node/edge upserts.
- [ ] Gate behind `KITTY_HISTORY_ENABLED` env var (opt-in, default off).

**Files:** `src/cartograph/indexing/indexer.py` (modify).

**Test scenarios:**
- Happy: `index_all` in a repo with commits populates all new fields.
- Edge: `index_changed` on a repo with no new commits since last index is a no-op (returns in <5 ms).
- Edge: env var unset → `update_history` skipped; nodes still indexed normally.

### Unit 5 — MCP tools

**State:** pending

- [ ] `src/cartograph/server/tools/history.py`:
      - `find_co_changed(qualified_name: str, limit: int = 10) -> list[{target_name, weight,
        kind, role, summary}]`
      - `get_change_history(qualified_name: str, limit: int = 20) -> {last_touched_at,
        change_frequency, recent_authors: list[email]}` — derived from `authored_by` edges and
        the node's own `last_touched_at`.
- [ ] Register both in `server/main.py`.

**Test scenarios:**
- Happy: `find_co_changed("cartograph.storage.graph_store::GraphStore::search")` returns nodes
  changed together with `search`.
- Edge: unknown symbol → empty list, not error.
- Edge: history disabled → tools return `{"error": "history indexing disabled"}`.

### Unit 6 — Commit-message → memory entries (optional)

**State:** pending

- [ ] Heuristics module: detect fix commits (`"fix:"`, `"fixes #"`, `"bug"`) and write a
      `litter_box` entry with category `failure`, description from the commit message, context
      = affected node list.
- [ ] Detect conventional-commit `feat:` / `refactor:` → `treat_box` entry with category
      `validated-pattern`.
- [ ] Gated behind `KITTY_HISTORY_MEMORY_ENABLED=true` (off by default; secondary opt-in).

**Files:** `src/cartograph/indexing/history_memory.py` (new),
`src/cartograph/memory/memory_store.py` (modify — add a `touch_litter_box_from_commit` helper).

**Test scenarios:**
- Happy: `fix: handle None in search` commit → litter-box entry referencing the touched nodes.
- Edge: non-conventional commit message → no memory entry.

### Unit 7 — Documentation

**State:** pending

- [ ] Update `README.md` commit-history section including the opt-in env vars.
- [ ] Update `CLAUDE.md` edge-kinds table.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md` with new tool docs.
- [ ] Update `plugins/kitty/skills/kitty-impact/SKILL.md` — co-change adds a new dimension to
      impact analysis ("what else tends to change with this function?").

**Files:** `README.md`, `CLAUDE.md`,
`plugins/kitty/skills/kitty/references/tool-reference.md`,
`plugins/kitty/skills/kitty-impact/SKILL.md` (modify).

## System-Wide Impact

- **Plugin surface:** +2 MCP tools (search, history).
- **Schema:** +2 columns on `nodes`, +2 edge kinds, +1 column on `graph_meta`.
- **Graph DB size:** adds `co_changed_with` edges (capped at `30 × node_count`). For 946 nodes,
  ≤28K edges, ~2 MB.
- **Index-time cost:** `git log --name-only` over 500 commits on this repo is ~200 ms. Amortized
  across incremental runs.
- **Privacy:** author emails are stored. Documented; opt-in default.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| `git log` output format varies between versions | Use explicit `--pretty=format:` with tab separators and `--no-merges`; CI asserts format |
| First-run on a 10k-commit repo is slow (minutes) | Cap at last 500 commits on first run; later runs are truly incremental |
| Co-change edges explode on monorepos that touch dozens of files per commit | Pruning in Unit 3 caps per-node and by weight; document the cap as a known limit |
| Author email leaks PII when repo is publicly shared (R8) | Document; R8 plan adds a `strip_author_emails` flag for artifact publishing |
| Sub-file attribution is too coarse | Explicitly acknowledge in docs; R2 can refine in v2 |

**Dependencies on other plans:** none strictly. Memory subsystem (`memory/memory_store.py`)
consumed in Unit 6 already exists.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R4)
- Predecessor plan: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (refreshed by this plan)
- Prior art (co-change analysis): "Using the Gini coefficient as a measure of unequal
  change-distribution" — D'Ambros et al., but simpler pair-count suffices for v1.

## Handoff

Ready for `kitty:work`. Entry point: Unit 1 (migration). Units 2–3 sequential; Unit 4
integrates them; Units 5–7 can parallelize once 4 lands. Unit 6 is optional.
