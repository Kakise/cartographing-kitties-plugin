---
title: Test-Coverage Edges (R5)
type: feat
status: active
date: 2026-05-04
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R5
units:
  - id: 1
    title: Migration
    state: pending
  - id: 2
    title: Heuristic pass
    state: pending
  - id: 3
    title: coverage.py JSON ingestion
    state: pending
  - id: 4
    title: nyc / Istanbul JSON ingestion
    state: pending
  - id: 5
    title: '`find_tests_for` MCP tool'
    state: pending
  - id: 6
    title: Agent & skill updates
    state: pending
  - id: 7
    title: Documentation
    state: pending
---

# Test-Coverage Edges — Implementation Plan (R5)

## Overview

Add a `tests` edge kind linking test functions to the symbols they exercise. Derived in two
passes: (1) heuristic — test function name matches target; (2) optional ground truth — parse
coverage JSON (`coverage.py` for Python, `nyc` / Istanbul for JS/TS). Surfaces a
`find_tests_for(symbol)` MCP tool and directly raises the accuracy of
`expert-kitten-testing`.

## Problem Frame

The brainstorm notes `expert-kitten-testing` accuracy is bounded by its inability to see which
tests actually cover a given symbol. Today the graph has no test-exercises-symbol relation; the
agent guesses by name-matching during review. Ground-truth coverage is available from standard
tools; folding it into the graph gives every consumer of the graph (skills, agents, human users)
the same precise view.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R5.a — `tests` edge kind in schema | Unit 1 |
| R5.b — Heuristic pass (name-based test matching) | Unit 2 |
| R5.c — coverage.py JSON ingestion pass (upgrades heuristic to ground truth) | Unit 3 |
| R5.d — `nyc` / Istanbul JSON ingestion pass for JS/TS | Unit 4 |
| R5.e — `find_tests_for(symbol)` MCP tool | Unit 5 |
| R5.f — `expert-kitten-testing` prompt update to use new tool | Unit 6 |

## Scope Boundaries

- **In scope:** Python (`coverage.py` JSON) and JS/TS (`nyc` / Istanbul JSON) coverage; heuristic
  fallback for any language; one new MCP tool.
- **Out of scope:** Running the test suite itself (plugin consumes pre-existing coverage files);
  per-line coverage visualization; differential coverage between runs; Go/Rust/Java coverage
  formats — accept heuristic-only for v1 (ground-truth pass per language is future work).

## Memory Context

No relevant memory entries found.

## Context & Research

### Extension Points

- `src/cartograph/storage/migrations/0006_test_coverage.sql` — new migration adding `tests` edge
  kind.
- `src/cartograph/indexing/coverage.py` — **new module** with heuristic + JSON parsers.
- `src/cartograph/server/tools/coverage.py` — **new module** for `find_tests_for`.
- `src/cartograph/indexing/indexer.py` — hook after node upserts to run coverage pass.
- `plugins/kitty/agents/expert-kitten-testing.md` — prompt updates to use the new tool.

### Heuristic Rules (v1 — conservative)

1. Test function `test_foo_does_bar` targets symbol `foo` in a sibling source file. Specifically:
   - A function under `tests/` whose name starts with `test_` or ends with `_test`.
   - Strip the `test_` prefix / `_test` suffix; if the remaining stem matches a function or method
     name in the same project, add a `tests` edge.
2. Test class `TestFoo::test_bar` targets class `Foo` in the source tree.
3. JS/TS: `describe('Foo', ...) { it('does bar', ...) }` — parse `describe` first arg; if it
   matches an exported symbol, add `tests` edges for each `it` inside.

Heuristic edges set `properties.source = "heuristic"`. Coverage-JSON pass replaces heuristic
edges by removing them and adding `properties.source = "coverage"` with a line-count weight.

### Coverage-JSON Formats (well-specified)

- **Python (`coverage.py`):** `coverage json` emits `{"files": {"path": {"executed_lines":
  [...], "contexts": {"line_no": ["test_context", ...]}}}}`. Context per line enables
  test-to-symbol attribution.
- **JS/TS (`nyc`):** Istanbul JSON format is `{filename: {fnMap: {...}, f: {fn_id:
  hit_count}, statementMap: {...}, s: {stmt_id: hit_count}}}`. No test-context attribution by
  default (nyc doesn't track which test hit which line). v1 falls back to heuristic-only for
  JS/TS if context is unavailable.

## Key Technical Decisions

### Heuristic-first, coverage-opt-in

Heuristic runs on every `index_all`. Coverage-JSON ingestion is triggered by explicit CLI:
`uv run python -m cartograph.indexing.coverage ingest <path>` and/or passed via
`KITTY_COVERAGE_JSON=path/to/coverage.json` env var picked up in the indexer.

Reason: coverage files don't exist until a test run happens, and agents shouldn't run tests as a
side effect of indexing.

### Edge-direction convention

`tests` edge: source = test node (the test function), target = exercised node. Same direction as
`calls` (source calls target). This keeps queries simple: `find_tests_for(target)` =
`find_dependents(target, edge_kinds=["tests"])`.

### Re-ingestion idempotency

Running coverage ingestion twice for the same coverage file yields the same edges. Achieve via:
1. Delete all `tests` edges where `source.file_path` starts with `tests/` before re-ingest.
2. Re-add edges from parsed JSON.

## Open Questions

### Resolve Before Implementing

- **Where does the heuristic pass look for test files?** Recommend: any file under a directory
  named `tests`, `test`, `__tests__`, `spec`, or with `.test.` / `.spec.` in the filename. Also
  respect pytest's `testpaths` from `pyproject.toml` if present.
- **Do we surface a `tests` weight?** Recommend: yes, weight = number of covered lines (from
  coverage JSON) or 1 (from heuristic). Enables `expert-kitten-testing` to prioritize "most
  thoroughly tested" vs. "barely touched".

### Defer

- Go `go test -coverprofile`, Rust `cargo tarpaulin`, Java JaCoCo ingestion. Add per-language
  parsers in a follow-up plan once R3 lands those languages.

## Implementation Units

### Unit 1 — Migration

**State:** pending

- [ ] `src/cartograph/storage/migrations/0006_test_coverage.sql`:
      - Relax edges CHECK to include `tests` (recreate-table pattern; may share migration with
        R4's CHECK relaxation if R4 is already merged — note the sequencing: if R4 migrated the
        CHECK, R5 modifies R4's recreation to include `tests` too).

**Verification:** inserting a `tests` edge succeeds; existing edges survive the migration.

### Unit 2 — Heuristic pass

**State:** pending

- [ ] `src/cartograph/indexing/coverage.py::run_heuristic(store: GraphStore) -> int`:
      1. Find all nodes in `testpaths` with names starting with `test_`.
      2. For each, strip prefix/suffix; look up the candidate target by name scan
         (`GraphStore.find_nodes(name=...)`).
      3. Add `tests` edge with `properties.source="heuristic"` and `weight=1`.
- [ ] Wire into `Indexer.index_all` and `index_changed` at the end of the pipeline.
      Gate behind `KITTY_HEURISTIC_TESTS_ENABLED=true` (default **on**).

**Files:** `src/cartograph/indexing/coverage.py` (new),
`src/cartograph/indexing/indexer.py` (modify).

**Test scenarios:**
- Happy: `test_search_returns_hits` test targeting `search` → edge created.
- Happy: `TestGraphStore::test_upsert_nodes` → edge to `GraphStore::upsert_nodes`.
- Edge: `test_helpers.py::test_foo` with no matching `foo` symbol → no edge, no error.
- Edge: name collision (two `foo` functions in different modules) → edges to both, let
  coverage-JSON pass resolve later.

### Unit 3 — coverage.py JSON ingestion

**State:** pending

- [ ] `src/cartograph/indexing/coverage.py::ingest_python_coverage(store, json_path) -> int`:
      1. Parse JSON with `contexts` block if present; else fall back to heuristic-only for Python
         too.
      2. For each file in the coverage, map covered line ranges to our nodes via
         `start_line`/`end_line`.
      3. For each covered-line context (`test_module::TestClass::test_method` or similar), locate
         the test node, add `tests` edge to each source node intersecting those lines.
      4. Remove any pre-existing heuristic `tests` edges from the *same test node* before adding
         the ground-truth edges.
- [ ] CLI: `uv run python -m cartograph.indexing.coverage python <json_path>`.

**Files:** `src/cartograph/indexing/coverage.py` (extend).

**Test scenarios:**
- Happy: fixture with coverage JSON → edges created with `properties.source="coverage"` and
  line-count weight.
- Happy: re-ingest same file → same edges (idempotent).
- Edge: coverage JSON without contexts → logs warning, falls back to per-file edge aggregation
  (all tests in the context map → all symbols in covered files), still better than nothing.

### Unit 4 — nyc / Istanbul JSON ingestion

**State:** pending

- [ ] `src/cartograph/indexing/coverage.py::ingest_istanbul_coverage(store, json_path) -> int`:
      1. Parse Istanbul JSON.
      2. Without `describe`-level attribution, produce file-level edges: every test file that
         covers ≥1 line of a source file → `tests` edge from the test file's top-level test
         nodes to the source file's top-level source nodes.
      3. Document the coarser granularity vs. Python in the module docstring.
- [ ] CLI: `uv run python -m cartograph.indexing.coverage js <json_path>`.

**Files:** `src/cartograph/indexing/coverage.py` (extend).

**Test scenarios:**
- Happy: Istanbul JSON from a small TS project → file-level edges created.
- Edge: malformed JSON → clear error message, no partial writes.

### Unit 5 — `find_tests_for` MCP tool

**State:** pending

- [ ] `src/cartograph/server/tools/coverage.py`:
      - `find_tests_for(qualified_name: str, limit: int = 20) -> list[{test_name, file_path,
        weight, source}]` — wraps `find_dependents(qualified_name, edge_kinds=["tests"])`.
- [ ] Register in `server/main.py`.

**Test scenarios:**
- Happy: returns heuristic test for `search`.
- Happy: after ingesting coverage JSON, returns coverage-sourced tests with higher weights
  before heuristic ones.
- Edge: symbol with no tests → empty list.

### Unit 6 — Agent & skill updates

**State:** pending

- [ ] `plugins/kitty/agents/expert-kitten-testing.md` — replace the "approximate test-to-symbol
      match by name" instruction with "call `find_tests_for(target_symbol)` first; if empty,
      then fall back to name-based search as a gap indicator".
- [ ] `plugins/kitty/skills/kitty-review/SKILL.md` — mention `find_tests_for` as the authoritative
      check for test coverage before review findings.

**Files:** `plugins/kitty/agents/expert-kitten-testing.md`,
`plugins/kitty/skills/kitty-review/SKILL.md` (modify).

### Unit 7 — Documentation

**State:** pending

- [ ] Update `README.md` coverage-ingest section with CLI usage.
- [ ] Update `CLAUDE.md` edge-kinds table.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md`.

**Files:** `README.md`, `CLAUDE.md`,
`plugins/kitty/skills/kitty/references/tool-reference.md` (modify).

## System-Wide Impact

- **Plugin surface:** +1 MCP tool.
- **Schema:** +1 edge kind.
- **Graph DB size:** moderate — `tests` edges, capped by number of test functions × targets.
- **Agent quality:** `expert-kitten-testing` gains ground-truth coverage visibility; this alone
  is the primary payoff.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Heuristic name matching creates noisy edges | Coverage-JSON pass replaces heuristic edges; users running tests get precision |
| coverage.py context collection is opt-in (`--cov-context`) and users forget to enable it | Document in README; degrade gracefully if contexts absent |
| Istanbul JSON is verbose for large repos | Stream-parse; reject files > 100 MB with a clear error |
| Renaming a test function leaves stale `tests` edges | Re-ingest replaces all heuristic edges from that test node; incremental coverage re-ingest matches file path prefix |

**Dependencies:** benefits from **R3** (language expansion) because Go/Java/Rust tests need
their own heuristic rules; can ship Python + JS/TS first with R3 still pending.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R5)
- Predecessor plan: `docs/plans/2026-04-23-006-feat-test-coverage-edges-plan.md` (refreshed by this plan)
- coverage.py contexts: https://coverage.readthedocs.io/en/latest/contexts.html
- Istanbul JSON schema: https://github.com/istanbuljs/schema

## Handoff

Ready for `kitty:work`. Entry point: Unit 1. Units 2, 3, 4 can parallelize post-migration.
Unit 5 depends on any coverage data existing. Units 6–7 are documentation and prompt updates.
