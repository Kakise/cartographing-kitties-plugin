---
title: Graph-Reactive Engineering
type: feat
status: active
date: 2026-03-28
origin: docs/brainstorms/2026-03-28-004-graph-reactive-engineering-requirements.md
---

# Graph-Reactive Engineering — Implementation Plan

## Overview

Transform Cartograph from a linear pipeline (brainstorm -> plan -> work -> review) into a graph-reactive loop (observe -> understand -> act -> validate -> compound). This requires:

- A lightweight schema migration system (no Alembic — custom migrator)
- 6 new MCP tools: `graph_diff`, `validate_graph`, `batch_query_nodes`, `get_context_summary`, `find_stale_annotations`, `rank_nodes`
- 3 modified tools: `index_codebase`, `annotation_status`, `submit_annotations`
- Schema changes: `graph_meta` table, `annotated_content_hash` + `graph_version` on nodes, `updated_at` on edges, definition-level content hashing
- Skill and agent markdown updates for the reactive loop workflow

## Problem Frame

The current pipeline treats the AST graph as a utility. The graph should be the central nervous system — driving a continuous loop where indexing produces diffs, diffs trigger understanding, understanding guides action, and validation catches structural issues before they ship.

## Requirements Trace

| Requirement | Implementation Unit |
|-------------|-------------------|
| R0 (Migration infra) | Unit 1 |
| R1 (graph_diff) | Unit 3 |
| R2 (validate_graph) | Unit 4 |
| R3 (batch_query_nodes) | Unit 5 |
| R4 (get_context_summary) | Unit 5 |
| R5 (find_stale_annotations) | Unit 6 |
| R6 (rank_nodes) | Unit 7 |
| R7 (existing tool mods) | Units 3, 6 |
| R8 (skill updates) | Units 8a, 8c |
| R9 (agent updates) | Unit 8b |

## Scope Boundaries

**In scope:** Everything in R0-R9 from the requirements doc, with Alembic replaced by a custom lightweight migrator.

**Out of scope:** Autonomous reactive loop triggering, graph-as-artifact (replacing markdown docs with graph annotations), git churn integration for importance scoring, LLM-powered annotation within the loop.

## Context & Research

### Key Findings from Research Agents

1. **No Alembic** — Alembic requires SQLAlchemy as a transitive dependency. Using a custom migrator instead: single-row `schema_version` table + ordered `.sql` migration files + ~50-line runner.

2. **Definition-level content hashing** — Currently only file nodes have `content_hash`. Definition nodes have `NULL`. Must compute hashes from tree-sitter source extraction (start_line/end_line) during `_index_files()`.

3. **Delete-before-reinsert pattern** — `index_changed()` deletes modified files' nodes before reinserting. Node IDs change. Version-based diff must use `qualified_name` as the stable join key, not node ID.

4. **Duplicate upsert methods** — `upsert_nodes()` and `bulk_insert_nodes()` have nearly identical SQL. Both need updating for new columns.

5. **Cross-file edge orphaning** — When file B is re-indexed but file A (which calls B) is not, call edges from A to B are silently lost. `validate_graph` should detect this.

6. **`_summarise_node` is the universal formatter** — 6 callers. All new tools should reuse it. Adding new fields (score, staleness) should be handled via optional enrichment, not by modifying the base helper.

### Patterns to Follow

- **Tool file:** Import `mcp` and `_main` from `server.main`, `@mcp.tool()` decorator, store guard check
- **Cross-module imports:** `analysis.py` imports `_summarise_node` from `query.py` — established pattern for `reactive.py`
- **GraphStore methods:** `clauses`/`params` dynamic WHERE, `_row_to_dict()` returns, `self._conn.commit()` after mutations
- **Tests:** Tools in `test_server.py` via `indexed_store` fixture, storage in `test_storage.py` via `_make_node` helper
- **Registration:** Import in `main.py` lines 59-63, update `expected_tools` set in `test_server.py:345`

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migration system | Custom lightweight migrator | Avoids SQLAlchemy dependency. Single-row `schema_version` table + ordered `.sql` files. ~50 lines Python. |
| `graph_version` storage | `graph_meta` table with `CHECK(id = 1)` | Global counter, not per-node. Single-row table is established SQLite pattern. |
| Version stamping | `graph_version INTEGER` column on nodes | Stamped during `_index_files()`. Enables diff queries via "nodes at version N-1 vs N". |
| Diff join key | `qualified_name` (not node ID) | Node IDs change across delete/reinsert cycles in `index_changed()`. Qualified names are stable. |
| Definition hashing | Compute from source text (start_line:end_line) | Tree-sitter already provides line ranges. Hash the extracted source for per-node staleness. |
| Edge timestamps | `updated_at TEXT` column on edges, DEFAULT NULL | Backfill existing as NULL. New/upserted edges get `datetime('now')`. |
| New tool file | `tools/reactive.py` for `graph_diff` + `validate_graph` | Loop-specific tools grouped together. Rest in existing files by domain. |
| Neighbor extraction | Extract `_gather_neighbors()` helper in `query.py` | Reused by both `query_node` and `batch_query_nodes`. Currently inline in `query_node`. |

## Open Questions

### Resolve Before Planning -> Resolved

- **graph_version storage:** Single-row `graph_meta` table with `CHECK(id = 1)` constraint.
- **Alembic integration:** Replaced with custom migrator. `create_connection()` calls `run_migrations(conn)` after pragmas.
- **Definition-level hashing:** Yes — compute hash from source text during `_index_files()`.

### Deferred to Implementation

- Should `validate_graph` auto-fix simple issues (e.g., remove dangling edges)?
- Should `rank_nodes` support custom weighting?
- How should the `needs_more_context` protocol handle cycles?

---

## Implementation Units

### Unit 1: Custom Schema Migration System

**Goal:** Replace the static `CREATE IF NOT EXISTS` approach with a versioned migration system that can handle ALTER TABLE operations.

**Requirements:** R0

**Dependencies:** None (foundation for all other units)

**Files:**
- Create `src/cartograph/storage/migrations/` directory
- Create `src/cartograph/storage/migrations/__init__.py`
- Create `src/cartograph/storage/migrations/runner.py` — migration runner (~50 lines)
- Create `src/cartograph/storage/migrations/0001_baseline.sql` — captures current SCHEMA_SQL
- Modify `src/cartograph/storage/connection.py` — call `run_migrations(conn)` after pragmas
- Modify `src/cartograph/storage/schema.py` — keep SCHEMA_SQL for reference, add `MIGRATION_TABLE_SQL`
- Create `tests/test_migrations.py` — migration runner tests

**Approach:**

The migration runner:
1. Creates `schema_version` table if not exists: `CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL DEFAULT 0)`
2. Reads current version from `schema_version`
3. Discovers `.sql` files in `migrations/` directory, sorted by number prefix
4. Executes all migrations with version > current version, in order
5. Updates `schema_version` after each successful migration
6. For fresh databases (no tables at all), the baseline migration (0001) runs the full `SCHEMA_SQL`
7. For existing databases (tables exist, no `schema_version`), detects this state and stamps as version 1 (baseline applied)

Integration with `create_connection()`:
```python
def create_connection(db_path, ...):
    conn = sqlite3.connect(db_path, ...)
    # ... pragmas ...
    run_migrations(conn)  # replaces conn.executescript(SCHEMA_SQL)
    return conn
```

The baseline migration (0001) contains the exact current `SCHEMA_SQL` content. Existing databases already have these tables, so `CREATE IF NOT EXISTS` is idempotent. New databases get the full schema.

**Patterns to follow:** The `create_connection()` contract must remain unchanged — callers get back a fully-schema-ready connection. The runner locates migrations relative to the package using `importlib.resources` or `Path(__file__).parent`.

**Test scenarios:**
- Happy path: Fresh DB, all migrations run in order, schema_version updated
- Happy path: Existing DB with tables but no schema_version, detected as baseline, stamped as v1
- Happy path: DB at version 1, new migration 0002 runs, version updated to 2
- Edge case: Empty migrations directory (only baseline) — no error
- Edge case: Migration with syntax error — transaction rolled back, version not updated
- Error path: Corrupt schema_version table — graceful error
- Integration: All existing tests pass unchanged (create_connection contract preserved)

**Verification:** `uv run pytest` passes. `create_connection()` returns identical schema for fresh DBs. Existing `.pawprints/graph.db` files are detected and stamped.

---

### Unit 2: Schema Changes (graph_meta, definition hashing, edge timestamps)

**Goal:** Add the schema infrastructure needed by all new tools: `graph_meta` table, `annotated_content_hash` column, `graph_version` column on nodes, `updated_at` on edges, and definition-level content hashing in the indexer.

**Requirements:** R1.1, R1.8 (partial), R5.1, R5.2

**Dependencies:** Unit 1 (migration runner)

**Files:**
- Create `src/cartograph/storage/migrations/0002_graph_reactive.sql` — the migration
- Modify `src/cartograph/storage/schema.py` — update `SCHEMA_SQL` to reflect final schema (for fresh DBs)
- Modify `src/cartograph/storage/graph_store.py` — update `upsert_nodes()`, `bulk_insert_nodes()`, `upsert_edges()`, `bulk_insert_edges()` for new columns; add `get_graph_version()`, `increment_graph_version()` methods
- Modify `src/cartograph/indexing/indexer.py` — compute definition-level `content_hash` in `_index_files()`, stamp `graph_version` on nodes/edges
- Modify `src/cartograph/annotation/annotator.py` — set `annotated_content_hash = content_hash` in `write_annotations()` for successful annotations
- Modify `tests/test_storage.py` — tests for new GraphStore methods and `_make_node` helper update
- Modify `tests/test_indexer.py` — verify definition nodes now have content_hash

**Approach:**

Migration 0002 SQL:
```sql
-- Graph metadata table (single-row, for global counters)
CREATE TABLE IF NOT EXISTS graph_meta (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    graph_version INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO graph_meta (id, graph_version) VALUES (1, 0);

-- Stale annotation detection
ALTER TABLE nodes ADD COLUMN annotated_content_hash TEXT;

-- Version stamping for graph diffs
ALTER TABLE nodes ADD COLUMN graph_version INTEGER DEFAULT 0;

-- Edge timestamps for diff detection
ALTER TABLE edges ADD COLUMN updated_at TEXT;

-- Backfill: set annotated_content_hash for already-annotated nodes
UPDATE nodes SET annotated_content_hash = content_hash WHERE annotation_status = 'annotated';

-- Index for version-based queries
CREATE INDEX IF NOT EXISTS idx_nodes_graph_version ON nodes(graph_version);
CREATE INDEX IF NOT EXISTS idx_edges_updated_at ON edges(updated_at);
```

Definition-level content hashing in `_index_files()`:
- After tree-sitter parsing extracts start_line/end_line for each definition, read those lines from the source text
- Compute SHA256 of the extracted source substring
- Set `content_hash` on definition node dicts (currently only file nodes get this)

GraphStore changes:
- `upsert_nodes()` and `bulk_insert_nodes()`: Add `annotated_content_hash` and `graph_version` to INSERT column lists. In ON CONFLICT clause, preserve `annotated_content_hash` when annotation status is preserved (same CASE pattern as existing `summary`/`properties`). Always update `graph_version` to `excluded.graph_version`.
- `upsert_edges()` and `bulk_insert_edges()`: Add `updated_at = datetime('now')` to ON CONFLICT clause.
- New method `get_graph_version() -> int`: `SELECT graph_version FROM graph_meta WHERE id = 1`
- New method `increment_graph_version() -> int`: `UPDATE graph_meta SET graph_version = graph_version + 1 WHERE id = 1 RETURNING graph_version`

Indexer changes:
- At the start of `index_all()` / `index_changed()`, call `store.increment_graph_version()` to get the new version number
- Pass version number to `_index_files()` as a parameter
- Stamp all node dicts with `graph_version = version`
- Stamp all edge upserts with the version (edges get `updated_at` via the ON CONFLICT clause automatically)

Annotator changes:
- In `write_annotations()`, when building the upsert dict for successful annotations (line 272-289), add `"annotated_content_hash": node.get("content_hash")`

**Test scenarios:**
- Happy path: Migration 0002 runs on existing DB, new columns added, graph_meta created
- Happy path: `increment_graph_version()` returns monotonically increasing values
- Happy path: Definition nodes get content_hash after indexing
- Happy path: `write_annotations()` sets `annotated_content_hash`
- Edge case: Fresh DB (0001 + 0002 both run) — all columns present from SCHEMA_SQL
- Edge case: Re-indexing preserves `annotated_content_hash` when annotation status preserved
- Integration: All existing tests pass with new columns (nullable defaults)

**Verification:** `uv run pytest` passes. Definition nodes have non-NULL `content_hash`. Graph version increments on each index run.

---

### Unit 3: `graph_diff` Tool + `index_codebase` Modification

**Goal:** The linchpin of the reactive loop. After re-indexing, returns what structurally changed. Also modifies `index_codebase` to include diff summary in its return.

**Requirements:** R1.2-R1.8, R7.1

**Dependencies:** Unit 2 (schema changes, `graph_version` column, `increment_graph_version()`)

**Files:**
- Create `src/cartograph/server/tools/reactive.py` — `graph_diff` tool
- Modify `src/cartograph/storage/graph_store.py` — add `get_diff(from_version, to_version, file_paths)` method
- Modify `src/cartograph/server/tools/index.py` — add `diff_available` and `diff_summary` to `index_codebase` return
- Modify `src/cartograph/server/main.py` — add `import cartograph.server.tools.reactive` + module-level `_last_index_version: int | None = None`
- Modify `tests/test_server.py` — add `TestGraphDiff` class, update `expected_tools`
- Modify `tests/test_storage.py` — add tests for `get_diff()`

**Approach:**

`GraphStore.get_diff(from_version, to_version, file_paths=None)`:
- **Nodes added:** `SELECT * FROM nodes WHERE graph_version = ? AND qualified_name NOT IN (SELECT qualified_name FROM ... at previous version)` — actually simpler: nodes where `graph_version = to_version` and no node with same `qualified_name` existed at `from_version`. Since we use `graph_version` stamping, nodes added = nodes with `graph_version = to_version` that are newly created (their `created_at` is recent).
- Better approach: Track the diff using the version stamps:
  - **Nodes added:** `graph_version = to_version AND created_at = updated_at` (created and updated at the same time = new)
  - **Nodes modified:** `graph_version = to_version AND created_at != updated_at` (existed before, updated now)
  - **Nodes removed:** Cannot be queried directly (they're deleted). Track via `_last_diff` in-memory dict.

Hybrid approach (recommended):
1. In `index_codebase`, before calling indexer, snapshot the set of `qualified_name` values for affected files
2. After indexing, compare against new state
3. Store the diff result in `_main._last_diff`
4. The `graph_diff` tool returns `_main._last_diff`

This combines the schema-based versioning (for knowing WHEN things changed across sessions) with in-memory snapshots (for accurate removed-node tracking within a session).

`tools/reactive.py` structure:
```python
"""Graph-reactive loop tools."""
from __future__ import annotations
from typing import Any
import cartograph.server.main as _main
from cartograph.server.main import mcp
from cartograph.server.tools.query import _summarise_node

@mcp.tool()
def graph_diff(file_paths: list[str] | None = None, include_edges: bool = True) -> dict[str, Any]:
    """Return what structurally changed in the last indexing run."""
    ...
```

`index_codebase` modification:
- Before indexing: snapshot qualified_names + edges for affected files
- After indexing: compute diff, store in `_main._last_diff`
- Return: add `"diff_available": True, "diff_summary": {"nodes_added": N, ...}`

**Test scenarios:**
- Happy path: Index, add a file, re-index, `graph_diff` shows new nodes
- Happy path: Index, modify a file (change function body), re-index, `graph_diff` shows modified nodes
- Happy path: Index, delete a file, re-index, `graph_diff` shows removed nodes
- Happy path: `file_paths` filter limits diff to specific files
- Happy path: `include_edges=False` omits edge-level diff
- Edge case: `graph_diff` before any indexing returns `{"error": "No diff available..."}`
- Edge case: Full re-index (all files) produces a valid diff
- Integration: `index_codebase` return includes `diff_available` and `diff_summary`

**Verification:** Call `index_codebase()`, modify fixture files, call `index_codebase()` again, call `graph_diff()` — shows accurate changes.

---

### Unit 4: `validate_graph` Tool

**Goal:** Structural health checks. Detects broken references, orphan nodes, and stale annotations after changes.

**Requirements:** R2

**Dependencies:** Unit 2 (schema changes for `annotated_content_hash`), Unit 3 (`_last_diff` for default scope)

**Files:**
- Modify `src/cartograph/server/tools/reactive.py` — add `validate_graph` tool
- Modify `src/cartograph/storage/graph_store.py` — add `validate_nodes()` method
- Modify `tests/test_server.py` — add `TestValidateGraph` class
- Modify `tests/test_storage.py` — add tests for `validate_nodes()`

**Approach:**

`GraphStore.validate_nodes(scope_file_paths=None, scope_qnames=None, checks=None)`:

Four checks, each a pure SQL query:

1. **`dangling_edges`**: Edges whose source or target node doesn't exist. Should not happen with FK constraints, but verifies integrity.
   ```sql
   SELECT e.*, 'source' as side FROM edges e
   LEFT JOIN nodes n ON e.source_id = n.id WHERE n.id IS NULL
   UNION ALL
   SELECT e.*, 'target' as side FROM edges e
   LEFT JOIN nodes n ON e.target_id = n.id WHERE n.id IS NULL
   ```

2. **`orphan_nodes`**: Non-file/module nodes with zero incoming edges (no `contains` edge from their file).
   ```sql
   SELECT n.* FROM nodes n
   LEFT JOIN edges e ON e.target_id = n.id
   WHERE n.kind NOT IN ('file', 'module') AND e.id IS NULL
   ```

3. **`missing_callees`**: Cross-file call edges that were lost due to partial re-indexing. Detect files that import another file but have no call edges despite the import. (Complex — may simplify to just checking for dangling references in the graph.)

4. **`stale_annotations`**: Nodes where `annotation_status = 'annotated'` AND `content_hash != annotated_content_hash` (or `annotated_content_hash IS NULL` for nodes annotated before the migration).
   ```sql
   SELECT n.* FROM nodes n
   WHERE n.annotation_status = 'annotated'
   AND (n.annotated_content_hash IS NULL OR n.content_hash != n.annotated_content_hash)
   ```

Scope filtering: when `scope_file_paths` or `scope_qnames` provided, add WHERE clauses. When neither provided and `_main._last_diff` exists, default to the changed files from last diff.

**Test scenarios:**
- Happy path: Clean graph passes all checks
- Happy path: Manually create a dangling edge (insert edge with bad target_id after disabling FK), detected
- Happy path: Create orphan node (definition with no `contains` edge), detected
- Happy path: Annotate a node, change its content_hash, stale_annotations detects it
- Edge case: Empty scope (no nodes to check) — passes trivially
- Edge case: `checks` parameter filters to specific checks only
- Integration: After `index_codebase()` + `graph_diff()`, `validate_graph()` uses last diff scope

**Verification:** Create known-bad graph state, `validate_graph` reports the issues with correct severity and location.

---

### Unit 5: `batch_query_nodes` + `get_context_summary` Tools

**Goal:** Efficient bulk context building for orchestrators. Replace N x `query_node` + N x `get_file_structure` with single calls.

**Requirements:** R3, R4

**Dependencies:** Unit 2 (schema changes for definition-level content_hash to enrich summaries)

**Files:**
- Modify `src/cartograph/server/tools/query.py` — add `batch_query_nodes`, `get_context_summary`, extract `_gather_neighbors()` helper
- Modify `src/cartograph/storage/graph_store.py` — add `context_summary()` method
- Modify `tests/test_server.py` — add `TestBatchQueryNodes`, `TestGetContextSummary` classes, update `expected_tools`
- Modify `tests/test_storage.py` — add tests for `context_summary()`

**Approach:**

Extract `_gather_neighbors(store, node_id) -> list[dict]` from the existing `query_node` implementation (lines 32-55 of query.py). This helper returns the list of neighbor dicts. Both `query_node` and `batch_query_nodes` call it.

`batch_query_nodes(names, include_neighbors=True)`:
```python
@mcp.tool()
def batch_query_nodes(names: list[str], include_neighbors: bool = True) -> dict[str, Any]:
    """Query multiple nodes in one call."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}
    found_nodes = []
    not_found = []
    for name in names:
        node = store.get_node_by_name(name)
        if node is None:
            matches = store.find_nodes(name=name)
            node = matches[0] if matches else None
        if node is None:
            not_found.append(name)
            continue
        result = _summarise_node(node)
        if include_neighbors:
            result["neighbors"] = _gather_neighbors(store, node["id"])
        found_nodes.append(result)
    return {"found": len(found_nodes), "not_found": not_found, "nodes": found_nodes}
```

`GraphStore.context_summary(file_paths=None, qualified_names=None, max_nodes=50)`:
- Single query: join nodes with edge count aggregation
- Group results by `file_path`
- Include in_degree (count of incoming edges) per node
- Return: `{file_path: [node_summaries_with_in_degree]}`

`get_context_summary(file_paths, qualified_names, include_edges, max_nodes)`:
- Calls `store.context_summary()` for the grouped node data
- If `include_edges=True`, queries edges between the selected nodes
- Returns compact grouped response

**Test scenarios:**
- Happy path: `batch_query_nodes(["Indexer", "GraphStore"])` returns both with neighbors
- Happy path: `batch_query_nodes(["nonexistent"])` returns in `not_found`
- Happy path: `get_context_summary(file_paths=["src/cartograph/storage/graph_store.py"])` returns grouped nodes with in_degree
- Happy path: `include_edges=True` includes edge list between nodes
- Edge case: `max_nodes` limits output
- Edge case: `include_neighbors=False` omits neighbor data
- Edge case: Mixed found/not_found names
- Integration: Response format consistent with existing `query_node` output

**Verification:** Compare `batch_query_nodes` output against individual `query_node` calls — same data, single call.

---

### Unit 6: `find_stale_annotations` Tool + Existing Tool Modifications

**Goal:** Detect nodes whose code changed since annotation. Modify `annotation_status` to include stale count and `submit_annotations` to set `annotated_content_hash`.

**Requirements:** R5, R7.2, R7.3

**Dependencies:** Unit 2 (schema changes for `annotated_content_hash`, definition-level content hashing)

**Files:**
- Modify `src/cartograph/server/tools/annotate.py` — add `find_stale_annotations` tool, modify `submit_annotations` to pass through `annotated_content_hash`
- Modify `src/cartograph/server/tools/index.py` — modify `annotation_status` to include `stale` count
- Modify `tests/test_server.py` — add `TestFindStaleAnnotations` class, update `expected_tools`, update existing annotation tests
- Modify `tests/test_storage.py` — add stale annotation detection tests

**Approach:**

`find_stale_annotations(file_paths=None, limit=50)`:
```python
@mcp.tool()
def find_stale_annotations(file_paths: list[str] | None = None, limit: int = 50) -> dict[str, Any]:
    """Find nodes whose code changed since they were annotated."""
    store = _main._store
    if store is None:
        return {"error": "Server not initialised"}
    # Query: annotated nodes where content_hash != annotated_content_hash
    stale = store.find_stale_nodes(file_paths=file_paths, limit=limit)
    return {
        "count": len(stale),
        "stale_nodes": [
            {**_summarise_node(n), "reason": "content_hash_changed"}
            for n in stale
        ],
    }
```

`GraphStore.find_stale_nodes(file_paths=None, limit=50)`:
```sql
SELECT * FROM nodes
WHERE annotation_status = 'annotated'
AND content_hash IS NOT NULL
AND (annotated_content_hash IS NULL OR content_hash != annotated_content_hash)
[AND file_path IN (...)]
LIMIT ?
```

`annotation_status` modification — add stale count:
```python
# Add to existing query
stale_cur = conn.execute("""
    SELECT COUNT(*) FROM nodes
    WHERE annotation_status = 'annotated'
    AND content_hash IS NOT NULL
    AND (annotated_content_hash IS NULL OR content_hash != annotated_content_hash)
""")
stale_count = stale_cur.fetchone()[0]
# Add to return dict: "stale": stale_count
```

`submit_annotations` modification — the `write_annotations()` function in `annotator.py` already sets `annotated_content_hash` (from Unit 2). The tool wrapper in `annotate.py` needs no changes beyond what Unit 2 provides. However, we need to import `_summarise_node` from query.py for the `find_stale_annotations` response.

**Test scenarios:**
- Happy path: Annotate a node, re-index with different content, `find_stale_annotations` finds it
- Happy path: `annotation_status` includes `stale` count
- Happy path: `submit_annotations` sets `annotated_content_hash` (verified by subsequent `find_stale_annotations` returning empty)
- Edge case: Node annotated before migration (annotated_content_hash is NULL) — detected as stale
- Edge case: `file_paths` filter limits scope
- Edge case: No stale annotations — returns `{"count": 0, "stale_nodes": []}`
- Integration: Full cycle: annotate -> modify code -> re-index -> find_stale_annotations -> re-annotate -> no stale

**Verification:** Annotate nodes, modify source, re-index, confirm stale detection. Re-annotate, confirm clean.

---

### Unit 7: `rank_nodes` Tool

**Goal:** PageRank-lite importance scoring. Enables weighted impact analysis and prioritized review.

**Requirements:** R6

**Dependencies:** Unit 2 (schema changes for enriched node data)

**Files:**
- Modify `src/cartograph/server/tools/analysis.py` — add `rank_nodes` tool
- Modify `src/cartograph/storage/graph_store.py` — add `rank_by_in_degree()` and `rank_by_transitive()` methods
- Modify `tests/test_server.py` — add `TestRankNodes` class, update `expected_tools`
- Modify `tests/test_storage.py` — add ranking tests

**Approach:**

`GraphStore.rank_by_in_degree(scope_file_paths=None, scope_qnames=None, kind=None, limit=20)`:
```sql
SELECT n.*, COUNT(e.id) as in_degree,
       (SELECT COUNT(*) FROM edges e2 WHERE e2.source_id = n.id) as out_degree
FROM nodes n
LEFT JOIN edges e ON e.target_id = n.id
[WHERE n.file_path IN (...)]
[AND n.kind = ?]
GROUP BY n.id
ORDER BY in_degree DESC
LIMIT ?
```

`GraphStore.rank_by_transitive(scope_qnames, limit=20)`:
- For each node in scope, call `reverse_dependencies()` and count results
- Return nodes sorted by transitive dependent count
- Cap scope to prevent expensive recursive queries on large graphs

`rank_nodes` tool:
```python
@mcp.tool()
def rank_nodes(
    scope: list[str] | None = None,
    kind: str | None = None,
    limit: int = 20,
    algorithm: str = "in_degree",
) -> dict[str, Any]:
    """Rank nodes by importance (in-degree or transitive dependents)."""
    ...
```

Return format enriches `_summarise_node` with `score`, `in_degree`, `out_degree`.

**Test scenarios:**
- Happy path: `rank_nodes()` returns nodes ordered by in_degree, highest first
- Happy path: `_summarise_node`-based callers like `find_dependents` have high in_degree
- Happy path: `kind="class"` filters to classes only
- Happy path: `algorithm="transitive"` uses recursive count
- Edge case: Isolated node (no edges) has score 0
- Edge case: `scope` limits to specific files
- Edge case: `limit=1` returns only the top node
- Integration: Scores match manual edge count verification

**Verification:** Compare `rank_nodes` output against manual `SELECT COUNT(*) FROM edges WHERE target_id = ?` queries.

---

### Unit 8a: Standardize Subgraph Context Across All Skills

**Goal:** Fix the inconsistent context delivery pattern. Currently only `kitty:review`, `kitty:plan`, and `kitty:annotate` build proper subgraph context for agents. `kitty:explore` and `kitty:impact` use direct tool invocation (agents call tools themselves — but agents *cannot* call MCP tools). `kitty:work` and `kitty:brainstorm` build partial context.

**Requirements:** R8.1-R8.7

**Dependencies:** Units 3-7 (all tools implemented)

**The Problem (from audit):**

| Skill | Context Delivery | Tools Used | Gap |
|-------|-----------------|------------|-----|
| kitty:review | Orchestrator-mediated, comprehensive | 6 of 9 | Missing `search` for semantic impact |
| kitty:plan | Orchestrator-mediated, comprehensive | 7 of 9 | Good — best example |
| kitty:annotate | Orchestrator-mediated | 4 of 9 | Good for its scope |
| kitty:brainstorm | Partial orchestrator-mediated | 5 of 9 | Missing `find_dependencies`, `find_dependents`, edges |
| kitty:work | Minimal orchestrator-mediated | 3 of 9 | **Missing blast radius, dependencies, annotation coverage** |
| kitty:explore | Direct tool invocation (broken) | 4 of 9 | **Agents can't call MCP tools — pattern is wrong** |
| kitty:impact | Direct tool invocation (broken) | 3 of 9 | **Agents can't call MCP tools — pattern is wrong** |

**Files:**
- Modify `plugins/kitty/skills/kitty-explore/SKILL.md` — rewrite from direct invocation to orchestrator-mediated
- Modify `plugins/kitty/skills/kitty-impact/SKILL.md` — rewrite from direct invocation to orchestrator-mediated
- Modify `plugins/kitty/skills/kitty-work/SKILL.md` — add full context building per worker
- Modify `plugins/kitty/skills/kitty-brainstorm/SKILL.md` — add missing dependency/dependent context
- Modify `plugins/kitty/skills/kitty-review/SKILL.md` — add `search` + `validate_graph` + `rank_nodes`
- Modify `plugins/kitty/skills/kitty-plan/SKILL.md` — add `batch_query_nodes`, `get_context_summary`, `rank_nodes`
- Modify `plugins/kitty/skills/kitty/SKILL.md` — router skill, document new tools

**Approach — per skill:**

**`kitty:explore` (rewrite):**
Current: agents call `get_file_structure`, `query_node`, `search` directly.
New: Orchestrator builds full context then presents it directly (no agent dispatch needed for exploration — the orchestrator IS the explorer):
1. Call `index_codebase(full=false)` to ensure graph is fresh
2. Call `annotation_status()` — warn if coverage <30%
3. Call `get_context_summary(file_paths=...)` for overview (new tool)
4. Call `batch_query_nodes(names=...)` for multi-symbol deep dive (new tool)
5. Call `find_dependents(name=..., max_depth=2)` for "who uses this?"
6. Call `find_dependencies(name=..., max_depth=2)` for "what does this depend on?"
7. Call `rank_nodes(scope=..., limit=10)` for "what's most important here?" (new tool)
8. Present structured results directly to user

**`kitty:impact` (rewrite):**
Current: agents call `find_dependents`, `query_node` directly.
New: Orchestrator pre-computes full impact context, dispatches `librarian-kitten-impact` agent:
1. Call `index_codebase(full=false)`
2. Call `annotation_status()` — warn if coverage <30%
3. Call `query_node(name=target)` for target symbol details
4. Call `find_dependents(name=target, max_depth=4)` for transitive blast radius
5. Call `find_dependencies(name=target, max_depth=3)` for upstream constraints
6. Call `rank_nodes(scope=dependent_files)` for weighted importance (new tool)
7. Call `validate_graph(scope=target_files)` for structural issues (new tool)
8. Format all as subgraph context per `subgraph-context-format.md`
9. Dispatch `librarian-kitten-impact` with full context

**`kitty:work` (enrich workers):**
Current: Workers get file structures + query results only.
New: Each worker gets blast radius awareness:
1. Existing: `get_file_structure` + `query_node` for each unit's files
2. **Add:** `find_dependents(name=key_symbol, max_depth=2)` per key symbol being modified — workers know what they might break
3. **Add:** `find_dependencies(name=key_symbol, max_depth=2)` — workers understand upstream constraints
4. **Add:** `annotation_status()` check — warn worker if target area has low annotation coverage
5. **Add:** `rank_nodes(scope=unit_files)` — workers know which nodes need extra care
6. **Add post-implementation:** `index_codebase()` → `graph_diff()` → `validate_graph()` as the VALIDATE step after each worker completes

**`kitty:brainstorm` (fill gaps):**
Current: Builds annotation status, search results, file structures, symbol details.
New: Add missing sections:
1. **Add:** `find_dependencies(name=target, max_depth=2)` for each key symbol — understand what the feature area depends on
2. **Add:** `find_dependents(name=target, max_depth=2)` — understand who depends on the feature area (scope implications)
3. **Add:** Include edges between target nodes in the subgraph context
4. **Add:** Pass dependency/dependent data to `librarian-kitten-researcher` (currently only gets file structures + search results)

**`kitty:review` (enhance):**
Current: Already good — 6 of 9 tools, comprehensive subgraph context.
New additions:
1. **Add:** `validate_graph(scope=changed_files)` as a structural pre-check before dispatching agents (new tool)
2. **Add:** `rank_nodes(scope=changed_files)` to include importance scores in context — reviewers focus P0 attention on high-importance nodes (new tool)
3. **Add:** `search(query=feature_keywords)` to find semantically related code that might be affected but not in the dependency graph
4. **Add:** Include importance scores in the subgraph context passed to all reviewer agents

**`kitty:plan` (enhance):**
Current: Already excellent — 7 of 9 tools.
New additions:
1. **Replace** N x `get_file_structure` + N x `query_node` with `get_context_summary(file_paths=...)` (new tool — more token-efficient)
2. **Replace** individual `query_node` calls with `batch_query_nodes(names=...)` (new tool)
3. **Add:** `rank_nodes(scope=target_files)` to include importance context for research agents (new tool)

**Test scenarios:**
- Manual: Invoke each skill and verify it calls the expected MCP tools in the expected order
- Manual: Verify agents receive subgraph context (not empty or partial)
- Manual: Verify `kitty:explore` no longer instructs agents to call MCP tools directly

**Verification:** Run each skill on this codebase. Check that the subgraph context passed to agents includes all specified sections.

---

### Unit 8b: Agent Adaptive Context Protocol

**Goal:** Add the `needs_more_context` protocol so agents can request additional graph context from the orchestrator, and define per-agent-type context templates so each agent gets the right shape of data.

**Requirements:** R9.1-R9.4

**Dependencies:** Unit 8a (standardized context delivery)

**Files:**
- Modify all 8 agent markdown files in `plugins/kitty/agents/`:
  - `librarian-kitten-researcher.md`
  - `librarian-kitten-pattern.md`
  - `librarian-kitten-flow.md`
  - `librarian-kitten-impact.md`
  - `expert-kitten-correctness.md`
  - `expert-kitten-testing.md`
  - `expert-kitten-impact.md`
  - `expert-kitten-structure.md`
- Modify `plugins/kitty/agents/cartographing-kitten.md` — annotator agent
- Modify skill files that dispatch agents to handle `needs_more_context` in returns

**Approach:**

**`needs_more_context` protocol:**

Add to ALL agent output contracts a new optional section:
```json
{
  "needs_more_context": [
    {"tool": "find_dependents", "args": {"name": "AuthMiddleware", "max_depth": 3}},
    {"tool": "get_file_structure", "args": {"file_path": "src/auth/sso.py"}},
    {"tool": "batch_query_nodes", "args": {"names": ["SessionStore", "TokenValidator"]}}
  ]
}
```

Skills that dispatch agents must:
1. Check returned output for `needs_more_context`
2. If present, call the requested MCP tools
3. Append results to the agent's context
4. Re-dispatch the agent with enriched context (second pass)
5. Cap at 1 follow-up pass to prevent cycles

**Per-agent-type context templates:**

Each agent type gets a specific shape of subgraph context optimized for its analysis:

| Agent | Primary Context | Secondary Context | New Tools to Use |
|-------|----------------|-------------------|-----------------|
| `librarian-kitten-researcher` | Full subgraph (all 6 sections) | Annotation coverage warning | `get_context_summary` (token-efficient overview) |
| `librarian-kitten-pattern` | Search results + file structures | Symbol details with neighbors | `batch_query_nodes` (multi-symbol) |
| `librarian-kitten-flow` | Call-edge chains (depth 3-4) with node roles | Entry point details | `find_dependencies(edge_kinds=["calls"])` at depth 4 |
| `librarian-kitten-impact` | Transitive dependents (depth 3-4) with roles/tags | Importance scores | `rank_nodes` + `find_dependents` |
| `expert-kitten-correctness` | Changed nodes + immediate callers/callees | Edge contracts between changed nodes | `batch_query_nodes` for changed + `validate_graph` results |
| `expert-kitten-testing` | Changed nodes + test file structures | Dependency chains from changed to test files | `find_dependents(edge_kinds=["imports","calls"])` |
| `expert-kitten-impact` | Changed nodes + transitive dependents (depth 3) with importance | Edge kind breakdown (inherits > imports > calls) | `rank_nodes` + pre-grouped dependents by edge kind |
| `expert-kitten-structure` | New file structures + neighboring module structures | Naming convention baselines from siblings | `get_context_summary` for structural overview |

**Edge kind risk classification** — add to agent context:
```
### Edge Risk Classification
- inherits: HIGH (contract changes propagate to all subclasses)
- imports: MEDIUM (API changes break importers)
- calls: LOW-MEDIUM (behavioral changes may affect callers)
- contains: LOW (internal restructuring)
- depends_on: MEDIUM (external dependency changes)
```

**Annotation coverage adaptive behavior** — add to all agents:
```
### Annotation Coverage: X%
If coverage < 30%: Treat graph summaries/roles/tags as unreliable. Fall back to source code reading for understanding. Flag in output that analysis confidence is reduced.
If coverage 30-70%: Use graph data where available, supplement with source reading for unannotated nodes.
If coverage > 70%: Trust graph summaries/roles/tags as primary intelligence source.
```

**Test scenarios:**
- Manual: Dispatch agent, verify it returns `needs_more_context` when context is insufficient
- Manual: Verify orchestrator handles the follow-up pass correctly
- Manual: Verify agents adapt behavior based on annotation coverage level

**Verification:** Run `kitty:plan` (dispatches 4 agents), verify each receives its tailored context template. Artificially provide incomplete context and verify `needs_more_context` is returned.

---

### Unit 8c: Tool Reference + Annotation Workflow Documentation

**Goal:** Document all 6 new tools and update annotation workflow for stale detection.

**Requirements:** R8.7

**Dependencies:** Units 3-7 (tools implemented)

**Files:**
- Modify `plugins/kitty/skills/kitty/references/tool-reference.md` — add 6 new tools, update 3 modified tools
- Modify `plugins/kitty/skills/kitty/references/annotation-workflow.md` — add stale detection re-annotation flow

**Approach:**

For each new tool, document:
- Name and one-line description
- Parameters with types, defaults, and descriptions
- Return format with example JSON
- Usage examples showing common patterns
- When to use vs. when NOT to use

Add annotation workflow section for staleness:
```
## Stale Annotation Re-annotation

After code changes:
1. Call `find_stale_annotations()` to discover nodes with outdated summaries
2. Call `get_pending_annotations(retry_failed=False)` — stale nodes appear as pending
3. Re-annotate stale nodes with `submit_annotations()`
4. Verify with `annotation_status()` — stale count should be 0
```

**Test scenarios:**
- Review: tool-reference.md documents all 15 tools (9 existing + 6 new)
- Review: Parameter names match actual tool signatures
- Review: Return format examples match actual tool output

**Verification:** Cross-reference tool-reference.md against registered tools in `test_server.py:expected_tools`.

---

## System-Wide Impact

| Layer | Impact | Files |
|-------|--------|-------|
| Storage | New migration system, 3 new columns, 1 new table, 4 modified methods | 6 files |
| Indexing | Definition-level content hashing, graph_version stamping | 1 file |
| Annotation | `annotated_content_hash` on write | 1 file |
| Server tools | 6 new tools, 3 modified tools, 1 new module, 1 extracted helper | 6 files |
| Server main | 1 new import, 1 new module-level var | 1 file |
| Tests | 6 new test classes, updated expected_tools, migration tests | 3 files |
| Skills | 7 rewritten/enhanced SKILL.md + 2 reference docs (explore/impact rewritten from direct-invocation to orchestrator-mediated) | 9 files |
| Agents | 9 updated agent files (new context templates, needs_more_context protocol, adaptive annotation coverage behavior) | 9 files |
| **Total** | | **~36 files** |

## Risks & Dependencies

| Risk | Severity | Mitigation |
|------|----------|------------|
| Migration runner breaks existing DBs | HIGH | Baseline migration uses same `CREATE IF NOT EXISTS`. Detect existing DBs and stamp as v1. Extensive test coverage. |
| Duplicate upsert SQL diverges | MEDIUM | Update both `upsert_nodes` and `bulk_insert_nodes` in the same commit. Consider extracting shared SQL in a future refactor. |
| Definition-level hashing performance | LOW | SHA256 of small source strings is negligible. Tree-sitter already parses the file. |
| Cross-file edge orphaning undetectable | MEDIUM | `validate_graph` can detect missing edges heuristically but cannot know what "should" exist without re-parsing. Flag as advisory, not error. |
| `_last_diff` lost on server restart | LOW | Expected behavior — diff is session-scoped. Schema-based `graph_version` provides cross-session context. |

## Sources & References

- Requirements: `docs/brainstorms/2026-03-28-004-graph-reactive-engineering-requirements.md`
- Architecture: `CLAUDE.md` (project root)
- Research: 4 librarian-kitten agents (architecture, patterns, flow, impact)
- Existing patterns: `src/cartograph/server/tools/analysis.py` (tool template), `tests/test_server.py` (test template)
