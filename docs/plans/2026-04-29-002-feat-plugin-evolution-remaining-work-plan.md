---
title: Plugin Evolution — Remaining Work
type: feat
status: in_progress
date: 2026-04-29
supersedes: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
aggregates:
  - docs/plans/2026-04-23-002-feat-hybrid-search-plan.md
  - docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md
  - docs/plans/2026-04-23-004-feat-language-expansion-plan.md
  - docs/plans/2026-04-23-005-feat-commit-history-plan.md
  - docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md
  - docs/plans/2026-04-23-007-feat-centrality-surface-plan.md
  - docs/plans/2026-04-23-008-feat-watch-mode-plan.md
  - docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md
  - docs/plans/2026-04-23-010-feat-annotation-quality-plan.md
  - docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md
units:
  - id: 1
    title: 'hybrid-search :: U1 (Dependency + migration scaffolding)'
    state: pending
  - id: 2
    title: 'hybrid-search :: U2 (Embedding generator module)'
    state: pending
  - id: 3
    title: 'hybrid-search :: U3 (Graph-centrality channel)'
    state: pending
  - id: 4
    title: 'hybrid-search :: U4 (RRF fusion in `GraphStore.search`)'
    state: pending
  - id: 5
    title: 'hybrid-search :: U5 (Embedding generation at annotation time)'
    state: pending
  - id: 6
    title: 'hybrid-search :: U6 (Evaluation harness & recall measurement)'
    state: pending
  - id: 7
    title: 'hybrid-search :: U7 (Documentation)'
    state: pending
  - id: 8
    title: 'lsp-bridge :: U1 (LSP client core)'
    state: pending
  - id: 9
    title: 'lsp-bridge :: U2 (Server registry and lifecycle)'
    state: pending
  - id: 10
    title: 'lsp-bridge :: U3 (Four MCP tools)'
    state: pending
  - id: 11
    title: 'lsp-bridge :: U4 (Edge provenance marking (offline))'
    state: pending
  - id: 12
    title: 'lsp-bridge :: U5 (Phantom-edge fixture and metric)'
    state: pending
  - id: 13
    title: 'lsp-bridge :: U6 (Documentation)'
    state: pending
  - id: 14
    title: 'language-expansion :: U1 (Go extractor)'
    state: pending
  - id: 15
    title: 'language-expansion :: U2 (Java extractor)'
    state: pending
  - id: 16
    title: 'language-expansion :: U3 (Rust extractor)'
    state: pending
  - id: 17
    title: 'language-expansion :: U4 (Mixed-language integration)'
    state: pending
  - id: 18
    title: 'language-expansion :: U5 (Documentation)'
    state: pending
  - id: 19
    title: 'commit-history :: U1 (Migration + schema changes)'
    state: pending
  - id: 20
    title: 'commit-history :: U2 (Git log parser)'
    state: pending
  - id: 21
    title: 'commit-history :: U3 (Co-change computation)'
    state: pending
  - id: 22
    title: 'commit-history :: U4 (Indexer integration)'
    state: pending
  - id: 23
    title: 'commit-history :: U5 (MCP tools)'
    state: pending
  - id: 24
    title: 'commit-history :: U6 (Commit-message → memory entries (optional))'
    state: pending
  - id: 25
    title: 'commit-history :: U7 (Documentation)'
    state: pending
  - id: 26
    title: 'test-coverage-edges :: U1 (Migration)'
    state: pending
  - id: 27
    title: 'test-coverage-edges :: U2 (Heuristic pass)'
    state: pending
  - id: 28
    title: 'test-coverage-edges :: U3 (coverage.py JSON ingestion)'
    state: pending
  - id: 29
    title: 'test-coverage-edges :: U4 (nyc / Istanbul JSON ingestion)'
    state: pending
  - id: 30
    title: 'test-coverage-edges :: U5 (`find_tests_for` MCP tool)'
    state: pending
  - id: 31
    title: 'test-coverage-edges :: U6 (Agent & skill updates)'
    state: pending
  - id: 32
    title: 'test-coverage-edges :: U7 (Documentation)'
    state: pending
  - id: 33
    title: 'centrality-surface :: U3 (`get_context_summary` pruning)'
    state: pending
  - id: 34
    title: 'centrality-surface :: U6 (Documentation)'
    state: pending
  - id: 35
    title: 'watch-mode :: U1 (Filesystem watcher)'
    state: pending
  - id: 36
    title: 'watch-mode :: U2 (Debounce + coalesce)'
    state: pending
  - id: 37
    title: 'watch-mode :: U3 (`subscribe_graph_changes` MCP tool (long-poll))'
    state: pending
  - id: 38
    title: 'watch-mode :: U4 (Latency benchmark)'
    state: pending
  - id: 39
    title: 'watch-mode :: U5 (Documentation)'
    state: pending
  - id: 40
    title: 'shared-graph-cache :: U1 (`publish_graph` tool)'
    state: pending
  - id: 41
    title: 'shared-graph-cache :: U2 (`pull_graph` tool)'
    state: pending
  - id: 42
    title: 'shared-graph-cache :: U3 (Manifest + versioning)'
    state: pending
  - id: 43
    title: 'shared-graph-cache :: U4 (CLI)'
    state: pending
  - id: 44
    title: 'shared-graph-cache :: U5 (Privacy strip helper)'
    state: pending
  - id: 45
    title: 'shared-graph-cache :: U6 (Documentation)'
    state: pending
  - id: 46
    title: 'annotation-quality :: U5 (Orchestrator prompt update)'
    state: complete
    implemented_in: c5d3e17
  - id: 47
    title: 'annotation-quality :: U6 (Documentation)'
    state: complete
    implemented_in: aaa393e
  - id: 48
    title: 'harness-context-engineering :: U2 (MCP context-shaping (output schemas, response_shape, token_budget,
      cursors, cleanable))'
    state: pending
  - id: 49
    title: 'harness-context-engineering :: U4 (Skill restructuring (progressive disclosure, frontmatter
      expansion, dynamic context))'
    state: pending
  - id: 50
    title: 'harness-context-engineering :: U5 (Agent specialization (tool perms, Sonnet model, scaling
      rules, output contract, spawn map))'
    state: pending
  - id: 51
    title: 'harness-context-engineering :: U6 (Codex first-class runtime parity)'
    state: pending
  - id: 52
    title: 'harness-context-engineering :: U7 (Memory + handoff + observability + smoke tests)'
    state: pending
---

# Plugin Evolution — Remaining Work (consolidated)

## Overview

This plan is a tracking index for every still-pending implementation unit across the plugin
evolution sub-plans. It supersedes `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
as the canonical "what's left to do" surface.

Each unit below points back at the source plan for design depth — this document holds only
goals, source pointers, and rollup state. Pick a unit, run `kitty:work` against the source
plan, and tick state through `scripts/plan_status.py set-unit` on both files (this consolidated
plan and the source plan).

## Problem Frame

The original R1–R9 roadmap (`docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`) is
stale: phases α–ε reference completion gates that have since shifted, and three of the nine
sub-plans (centrality-surface, annotation-quality, harness-context-engineering) are now in
mid-flight. The roadmap is preserved in git for context but no longer the place to track
remaining work.

This consolidated plan replaces it with a flat list of remaining units derived directly from
the per-plan state. Re-running `scripts/plan_status.py audit` regenerates the inventory if it
drifts.

## Sequencing

The phase ordering from the old roadmap remains a useful execution guide where it still
applies:

- **Phase α — Retrieval foundation:** finish centrality-surface (U3, U6) and annotation-quality
  (U5, U6). These unblock the dense-search corpus that hybrid-search consumes.
- **Phase β — Hybrid search:** the seven hybrid-search units land next; they consume the
  centrality field and the cleaned summaries from the α phase.
- **Phase γ — Differentiation:** commit-history (R6 in the roadmap) — schema-additive, can run
  parallel with later phases.
- **Phase δ — Polyglot:** language-expansion (Go → Java → Rust order) followed by
  test-coverage-edges (heuristic pass, then per-language coverage JSON).
- **Phase ε — Precision:** lsp-bridge — highest effort; deliberately last in retrieval
  precision because hybrid-search RRF already covers most cases.
- **Phase ζ — DX:** watch-mode and shared-graph-cache; can ship in parallel with γ–ε.
- **Phase η — Harness context:** finish harness-context-engineering U2, U4–U7. These touch
  cross-cutting infrastructure (MCP shaping, skill restructuring, agent specialization, Codex
  parity, observability) and should land alongside the feature work where they intersect.

## Implementation Units

### Unit 1 — hybrid-search :: U1 (Dependency + migration scaffolding)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 2 — hybrid-search :: U2 (Embedding generator module)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 3 — hybrid-search :: U3 (Graph-centrality channel)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 4 — hybrid-search :: U4 (RRF fusion in `GraphStore.search`)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 5 — hybrid-search :: U5 (Embedding generation at annotation time)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 6 — hybrid-search :: U6 (Evaluation harness & recall measurement)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 7 — hybrid-search :: U7 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-002-feat-hybrid-search-plan.md` (Unit 7)
- [ ] Reference: see source plan for full design.

### Unit 8 — lsp-bridge :: U1 (LSP client core)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 9 — lsp-bridge :: U2 (Server registry and lifecycle)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 10 — lsp-bridge :: U3 (Four MCP tools)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 11 — lsp-bridge :: U4 (Edge provenance marking (offline))

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 12 — lsp-bridge :: U5 (Phantom-edge fixture and metric)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 13 — lsp-bridge :: U6 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 14 — language-expansion :: U1 (Go extractor)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 15 — language-expansion :: U2 (Java extractor)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 16 — language-expansion :: U3 (Rust extractor)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 17 — language-expansion :: U4 (Mixed-language integration)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 18 — language-expansion :: U5 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 19 — commit-history :: U1 (Migration + schema changes)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 20 — commit-history :: U2 (Git log parser)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 21 — commit-history :: U3 (Co-change computation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 22 — commit-history :: U4 (Indexer integration)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 23 — commit-history :: U5 (MCP tools)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 24 — commit-history :: U6 (Commit-message → memory entries (optional))

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 25 — commit-history :: U7 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-005-feat-commit-history-plan.md` (Unit 7)
- [ ] Reference: see source plan for full design.

### Unit 26 — test-coverage-edges :: U1 (Migration)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 27 — test-coverage-edges :: U2 (Heuristic pass)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 28 — test-coverage-edges :: U3 (coverage.py JSON ingestion)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 29 — test-coverage-edges :: U4 (nyc / Istanbul JSON ingestion)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 30 — test-coverage-edges :: U5 (`find_tests_for` MCP tool)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 31 — test-coverage-edges :: U6 (Agent & skill updates)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 32 — test-coverage-edges :: U7 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (Unit 7)
- [ ] Reference: see source plan for full design.

### Unit 33 — centrality-surface :: U3 (`get_context_summary` pruning)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-007-feat-centrality-surface-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 34 — centrality-surface :: U6 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-007-feat-centrality-surface-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 35 — watch-mode :: U1 (Filesystem watcher)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-008-feat-watch-mode-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 36 — watch-mode :: U2 (Debounce + coalesce)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-008-feat-watch-mode-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 37 — watch-mode :: U3 (`subscribe_graph_changes` MCP tool (long-poll))

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-008-feat-watch-mode-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 38 — watch-mode :: U4 (Latency benchmark)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-008-feat-watch-mode-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 39 — watch-mode :: U5 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-008-feat-watch-mode-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 40 — shared-graph-cache :: U1 (`publish_graph` tool)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 1)
- [ ] Reference: see source plan for full design.

### Unit 41 — shared-graph-cache :: U2 (`pull_graph` tool)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 42 — shared-graph-cache :: U3 (Manifest + versioning)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 3)
- [ ] Reference: see source plan for full design.

### Unit 43 — shared-graph-cache :: U4 (CLI)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 44 — shared-graph-cache :: U5 (Privacy strip helper)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 45 — shared-graph-cache :: U6 (Documentation)

**State:** pending

- [ ] Source: `docs/plans/2026-04-23-009-feat-shared-graph-cache-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 46 — annotation-quality :: U5 (Orchestrator prompt update)

**State:** complete — implemented in c5d3e17

- [ ] Source: `docs/plans/2026-04-23-010-feat-annotation-quality-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 47 — annotation-quality :: U6 (Documentation)

**State:** complete — implemented in aaa393e

- [ ] Source: `docs/plans/2026-04-23-010-feat-annotation-quality-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 48 — harness-context-engineering :: U2 (MCP context-shaping (output schemas, response_shape, token_budget, cursors, cleanable))

**State:** pending

- [ ] Source: `docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md` (Unit 2)
- [ ] Reference: see source plan for full design.

### Unit 49 — harness-context-engineering :: U4 (Skill restructuring (progressive disclosure, frontmatter expansion, dynamic context))

**State:** pending

- [ ] Source: `docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md` (Unit 4)
- [ ] Reference: see source plan for full design.

### Unit 50 — harness-context-engineering :: U5 (Agent specialization (tool perms, Sonnet model, scaling rules, output contract, spawn map))

**State:** pending

- [ ] Source: `docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md` (Unit 5)
- [ ] Reference: see source plan for full design.

### Unit 51 — harness-context-engineering :: U6 (Codex first-class runtime parity)

**State:** pending

- [ ] Source: `docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md` (Unit 6)
- [ ] Reference: see source plan for full design.

### Unit 52 — harness-context-engineering :: U7 (Memory + handoff + observability + smoke tests)

**State:** pending

- [ ] Source: `docs/plans/2026-04-27-003-feat-harness-context-engineering-plan.md` (Unit 7)
- [ ] Reference: see source plan for full design.

## System-Wide Impact

See each source plan's "System-Wide Impact" section. The consolidated plan does not introduce
its own system-wide changes; it is a tracking artifact only.

## Risks & Dependencies

See each source plan. Cross-cutting risks remain those captured in
`docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md` (preserved in git).

## Sources & References

- Old roadmap (superseded): `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
- Source plans: see `aggregates:` in frontmatter.
- Audit tool: `scripts/plan_status.py audit`.
- Convention doc: `docs/architecture/plan-state-conventions.md` (added in Unit 7 of the
  meta-plan).

## Handoff

Pick a unit. Open the source plan named in its body. Run `kitty:work` against the source
plan's unit. When done, call:

```
uv run python scripts/plan_status.py set-unit <source-plan> <source-unit-id> complete --commit <hash>
uv run python scripts/plan_status.py set-unit docs/plans/2026-04-29-002-feat-plugin-evolution-remaining-work-plan.md <consolidated-unit-id> complete --commit <hash>
```

The audit hook will fail pre-commit if either is left out of sync.
