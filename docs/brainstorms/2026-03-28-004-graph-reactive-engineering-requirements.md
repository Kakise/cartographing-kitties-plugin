# Graph-Reactive Engineering — Requirements

## Problem Frame

Cartograph's current workflow is a rigid linear pipeline (brainstorm -> plan -> work -> review) inherited from compound-engineering. This treats the AST graph as a utility bolted onto a text-first workflow rather than as the central nervous system. The pipeline forces stage-gated file artifacts (requirements.md, plan.md) that become stale during implementation, offers no structural validation after changes, and loses all knowledge between sessions.

Real engineering is iterative — you discover things during implementation that invalidate the plan. The graph should drive the loop, not be a side tool.

**Who benefits:** AI coding agents using Cartograph's MCP tools. They get a continuous observe-understand-act-validate loop instead of a rigid pipeline, structural validation after every change, importance-weighted context, and compounding knowledge across sessions.

## Codebase Context

### Architecture (from Cartographing Kittens research)

4-layer stack with unidirectional dependencies:
- **Storage**: SQLite with WAL, FTS5, recursive CTEs. `GraphStore` class (389 lines) wraps raw `sqlite3.Connection`. Schema defined as `SCHEMA_SQL` string with `CREATE IF NOT EXISTS`. No migration system.
- **Indexing**: `Indexer` class with `index_all()` / `index_changed()` -> `_index_files()` (300-line core). Returns `IndexStats` dataclass.
- **Annotation**: Pure data-gathering layer. `get_pending_nodes()` / `write_annotations()`. No LLM calls — host agent generates summaries.
- **MCP Server**: FastMCP with `@mcp.tool()` decorator. 13 tools across 5 modules. Module-level `_store` / `_root` globals set by lifespan context manager.

### Key Constraints
- No schema migration system — need to introduce Alembic (raw SQL mode)
- No graph snapshots/versioning — no `updated_at` on edges, no diff mechanism
- `content_hash` exists on definition nodes (from tree-sitter) but `annotated_content_hash` does not
- `upsert_nodes` preserves annotation status when content changes — `content_hash` changes but `annotation_status` stays `annotated`, creating detectable staleness
- Node/edge kinds are CHECK-constrained in schema
- `_summarise_node` is the universal response formatter (6 callers)

### Existing Patterns (to follow)
- Tool registration: `@mcp.tool()` decorator, import `mcp` and `_main` from `cartograph.server.main`
- Store access: `_main._store` guard check at top of every tool
- Returns: `dict[str, Any]` — `{"error": "..."}` for errors, domain-specific for success
- Storage: `_row_to_dict()` conversion, `clauses`/`params` dynamic WHERE, recursive CTEs for traversal
- Testing: tools tested in `test_server.py` via `indexed_store` fixture, storage in `test_storage.py`
- Lazy imports for heavy domain modules inside tool functions
- When adding tools: import in `main.py` (lines 59-63), update `expected_tools` in `test_server.py`

## Requirements

### R0. Schema Migration Infrastructure

- R0.1. Introduce Alembic with raw SQL migrations (no SQLAlchemy models)
- R0.2. Add `alembic` as a project dependency
- R0.3. Create initial migration that captures current `SCHEMA_SQL` as baseline
- R0.4. Integrate migration execution into `create_connection()` flow so migrations run on every DB open
- R0.5. All subsequent schema changes (R5.x) delivered as numbered Alembic migrations

### R1. `graph_diff` Tool — OBSERVE Phase

The linchpin of the reactive loop. Returns what structurally changed after re-indexing.

- R1.1. Add `graph_version` counter column to nodes table and `updated_at` column to edges table via Alembic migration
- R1.2. Increment graph version on each indexing run; stamp nodes/edges created or modified in that run
- R1.3. Register `graph_diff` tool in new `tools/reactive.py` module
- R1.4. Parameters: `file_paths: list[str] | None = None`, `include_edges: bool = True`
- R1.5. Returns structured diff: `nodes_added`, `nodes_removed`, `nodes_modified`, `edges_added`, `edges_removed`, plus `summary` counts
- R1.6. Scoping: when `file_paths` provided, limit diff to those files; `None` = all changes from last index run
- R1.7. Modify `index_codebase` tool to include `diff_available: bool` and `diff_summary` in return value
- R1.8. Add `GraphStore` methods: `get_graph_version()`, `increment_graph_version()`, `get_diff(from_version, to_version, file_paths)`

### R2. `validate_graph` Tool — VALIDATE Phase

Structural health checks. Detects broken references after changes.

- R2.1. Register `validate_graph` tool in `tools/reactive.py`
- R2.2. Parameters: `scope: list[str] | None = None` (qualified names or file paths), `checks: list[str] | None = None`
- R2.3. Available checks: `dangling_edges`, `orphan_nodes`, `missing_callees`, `stale_annotations`
- R2.4. When `scope` is None, default to last diff's changed nodes (requires R1)
- R2.5. Returns: `passed: bool`, `issues: list[{check, severity, message, ...}]`, `summary: {checks_run, errors, warnings, passed}`
- R2.6. Add `GraphStore.validate_nodes()` method with pure SQL queries:
  - Dangling edges: edges whose target node no longer exists
  - Orphan nodes: non-file/module nodes with zero incoming edges
  - Missing callees: call edges where target was deleted
  - Stale annotations: nodes where `content_hash != annotated_content_hash` (depends on R5)

### R3. `batch_query_nodes` Tool — UNDERSTAND Phase

Query multiple nodes in one call for efficient orchestrator context building.

- R3.1. Register `batch_query_nodes` in existing `tools/query.py`
- R3.2. Parameters: `names: list[str]` (qualified or partial names), `include_neighbors: bool = True`
- R3.3. Returns: `found: int`, `not_found: list[str]`, `nodes: list[{...node + neighbors}]`
- R3.4. Reuse existing `_summarise_node` helper for consistent response format
- R3.5. Use existing `get_node_by_name` / `find_nodes` for resolution, batched

### R4. `get_context_summary` Tool — UNDERSTAND Phase

Token-efficient context for feeding into agents. Replaces N x `get_file_structure` + N x `query_node`.

- R4.1. Register `get_context_summary` in existing `tools/query.py`
- R4.2. Parameters: `file_paths: list[str] | None`, `qualified_names: list[str] | None`, `include_edges: bool = False`, `max_nodes: int = 50`
- R4.3. Returns: nodes grouped by file path with compact metadata (qualified_name, kind, name, role, summary, in_degree, tags), plus optional edge list
- R4.4. Add `GraphStore.context_summary()` method — single query joining nodes + edge counts, grouped by file_path

### R5. `find_stale_annotations` Tool — COMPOUND Phase

Finds nodes whose code changed since they were last annotated.

- R5.1. Add `annotated_content_hash TEXT` column to `nodes` table via Alembic migration
- R5.2. Backfill: `UPDATE nodes SET annotated_content_hash = content_hash WHERE annotation_status = 'annotated'`
- R5.3. Modify `write_annotations()` in `annotator.py` to set `annotated_content_hash = content_hash` when writing successful annotations
- R5.4. Register `find_stale_annotations` in existing `tools/annotate.py`
- R5.5. Parameters: `file_paths: list[str] | None = None`, `limit: int = 50`
- R5.6. Returns: `count: int`, `stale_nodes: list[{qualified_name, kind, summary, reason}]`
- R5.7. Staleness detection uses definition-level `content_hash` (not file-level) for precision
- R5.8. Modify `annotation_status` tool to include `stale: int` count in response
- R5.9. Modify `submit_annotations` tool to set `annotated_content_hash` on write

### R6. `rank_nodes` Tool — UNDERSTAND Phase

PageRank-lite importance scoring.

- R6.1. Register `rank_nodes` in existing `tools/analysis.py`
- R6.2. Parameters: `scope: list[str] | None` (file paths or qualified names), `kind: str | None`, `limit: int = 20`, `algorithm: str = "in_degree"`
- R6.3. Algorithms: `in_degree` (fast COUNT query), `transitive` (recursive CTE count, capped scope)
- R6.4. Returns: `ranked: list[{qualified_name, kind, name, file_path, score, in_degree, out_degree, summary, role}]`
- R6.5. Add `GraphStore.rank_by_in_degree()` method

### R7. Modifications to Existing Tools

- R7.1. `index_codebase` — add `diff_available: bool` and `diff_summary` to return (ties to R1)
- R7.2. `annotation_status` — add `stale: int` count (ties to R5)
- R7.3. `submit_annotations` — set `annotated_content_hash = content_hash` on successful writes (ties to R5)

### R8. Skill Updates — Reactive Loop Integration

- R8.1. Update `kitty` router skill SKILL.md to document new tools and the reactive loop workflow
- R8.2. Update `kitty-explore` skill to use `get_context_summary` and `batch_query_nodes` for richer exploration
- R8.3. Update `kitty-impact` skill to use `validate_graph` and `rank_nodes` for weighted impact analysis
- R8.4. Update `kitty-annotate` skill to use `find_stale_annotations` for re-annotation workflows
- R8.5. Update `kitty-work` skill to integrate the observe-understand-act-validate loop using `graph_diff` + `validate_graph`
- R8.6. Update `kitty-review` skill to use `validate_graph` for structural checks alongside agent-based review
- R8.7. Update tool reference doc (`references/tool-reference.md`) with all new tool parameters and returns

### R9. Agent Updates — Adaptive Context Feeding

- R9.1. Define `needs_more_context` protocol in agent output contracts: agents can include `{"needs": ["find_dependents(X)", "get_file_structure(Y)"]}` in their output
- R9.2. Create per-agent-type context templates using `get_context_summary`:
  - Flow analyzer: call-edge chains (depth 4)
  - Pattern analyst: search results + file structures
  - Impact analyst: transitive dependents + blast radius
  - Correctness reviewer: modified nodes + immediate callers/callees
- R9.3. Update all agent markdown files with the new output contract and context template expectations
- R9.4. Document the two-pass context feeding pattern: lightweight seed first, follow-up on `needs_more_context`

## Success Criteria

- All 6 new tools callable via MCP and returning correct structured responses
- `graph_diff` produces accurate diffs after incremental re-indexing (verified by adding/removing/modifying code and checking diff output)
- `validate_graph` detects dangling edges when a called function is deleted
- `find_stale_annotations` correctly identifies nodes whose code changed since annotation
- `rank_nodes` returns nodes ordered by in-degree with correct scores
- Alembic migrations run automatically on DB open, upgrading existing `.pawprints/graph.db` files
- All existing tests pass; new tests added for each new tool and storage method
- Skills reference new tools in their workflows
- Agent output contract includes `needs_more_context` protocol

## Scope Boundaries

### In scope
- 6 new MCP tools: `graph_diff`, `validate_graph`, `batch_query_nodes`, `get_context_summary`, `find_stale_annotations`, `rank_nodes`
- 3 modified tools: `index_codebase`, `annotation_status`, `submit_annotations`
- Alembic integration for schema migrations (raw SQL mode)
- Schema changes: `annotated_content_hash`, `graph_version`, `updated_at` on edges
- New `tools/reactive.py` module for loop-specific tools
- Skill SKILL.md updates for all affected skills
- Agent markdown updates for adaptive context protocol
- Tool reference documentation updates
- Tests for all new tools and storage methods

### Out of scope
- Actual reactive loop orchestration (the skills describe the loop; autonomous triggering is future work)
- Graph-as-artifact (replacing requirements.md/plan.md with graph annotations — future evolution)
- Git churn integration for importance scoring (future enhancement to `rank_nodes`)
- LLM-powered annotation within the reactive loop (existing annotation workflow handles this)
- UI/visualization for graph diffs or validation results

## Key Decisions

- **Schema migrations via Alembic (raw SQL)**: Adds a dependency but provides versioned, reversible migrations. Essential since we need ALTER TABLE for `annotated_content_hash`, `graph_version`, and `updated_at` columns.
- **Schema-based versioning for graph_diff**: Persists diff information across sessions via `graph_version` counter and timestamps. More robust than in-memory snapshots.
- **File layout: split approach**: `graph_diff` + `validate_graph` in new `tools/reactive.py` (loop-specific tools). `batch_query_nodes` + `get_context_summary` in existing `query.py`. `find_stale_annotations` in existing `annotate.py`. `rank_nodes` in existing `analysis.py`.
- **Definition-level staleness detection**: Use per-node `content_hash` (from tree-sitter source extraction) compared against `annotated_content_hash` for precise staleness. No over-reporting from file-level changes.
- **Full scope**: Both tool implementation (Phases 1-5) and skill/agent updates (Phase 6) in one effort. Tools land first, skills update after.

## Open Questions

### Resolve Before Planning
- Should `graph_version` be a separate table (single-row counter) or a column on a metadata table? Single-row table is simplest but unusual.
- Should Alembic's `env.py` use the existing `create_connection()` or manage its own connection? Preference toward integration to keep WAL pragmas consistent.

### Deferred
- Should `validate_graph` auto-fix simple issues (e.g., remove dangling edges) or only report?
- Should `rank_nodes` support custom weighting (e.g., user-specified edge kinds to count)?
- How should the `needs_more_context` protocol handle cycles (agent keeps requesting more context)?
- Should graph annotations (lessons, caveats, patterns) get their own edge/node kinds, or reuse the existing annotation fields (summary, tags, role)?

## Implementation Order

| Phase | What | Key Files |
|-------|------|-----------|
| 0 | Alembic setup + baseline migration | `alembic/`, `schema.py`, `connection.py`, `pyproject.toml` |
| 1 | `graph_diff` + schema versioning | `indexer.py`, `graph_store.py`, `tools/reactive.py`, `main.py` |
| 2 | `validate_graph` | `graph_store.py`, `tools/reactive.py` |
| 3 | `batch_query_nodes` + `get_context_summary` | `graph_store.py`, `tools/query.py` |
| 4 | `rank_nodes` | `graph_store.py`, `tools/analysis.py` |
| 5 | `find_stale_annotations` + schema + annotation changes | `schema.py` (migration), `annotator.py`, `tools/annotate.py`, `tools/index.py` |
| 6 | Skill + agent markdown updates | All skill and agent `.md` files |

## Verification

After each phase:
- `uv run pytest` — all existing + new tests pass
- `uv run ruff check src/` — lint clean
- `uv run basedpyright --level error` — type check clean
- `uv run codespell src` — no typos
- Manual: `uv run python -m cartograph.server.main` -> call new tools via MCP
