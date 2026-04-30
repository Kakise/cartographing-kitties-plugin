---
title: Web Graph Explorer — Separate Entrypoints
type: feat
status: complete
date: 2026-03-28
implemented_in: 5ad1145
units:
  - id: 1
    title: Add `check_same_thread` to `create_connection()`
    state: complete
    implemented_in: 5ad1145
  - id: 2
    title: Create `serve()` entrypoint and simplify `main()`
    state: complete
    implemented_in: 5ad1145
  - id: 3
    title: Tests
    state: complete
    implemented_in: 5ad1145
---

# Web Graph Explorer — Implementation Plan (Revised)

## Overview

Split the CLI into two dedicated entrypoints matching `pyproject.toml`:

- `cartographing-kittens` (`cartograph:main`) — MCP server only
- `kitty-graph` (`cartograph:serve`) — web graph explorer only

The `kitty-graph` entrypoint is already declared in `pyproject.toml` but points to a non-existent `serve()` function. This plan fixes that and cleans up the architecture.

## Problem Frame

The current `main()` function overloads two concerns (MCP server + web explorer) behind a `--serve` flag. The `pyproject.toml` already declares separate entrypoints, but only `main()` exists. The web server path also bypasses `create_connection()`, missing WAL mode and performance pragmas.

## Requirements

- R1. `kitty-graph` launches the web explorer directly (no flags needed)
- R2. `kitty-graph --port N` and `kitty-graph --project-root PATH` configure the server
- R3. `cartographing-kittens` becomes MCP-only (remove `--serve`, `--port`, `--project-root`)
- R4. Web server uses `create_connection()` with `check_same_thread=False` support
- R5. Existing web server functionality (API, frontend) unchanged
- R6. Graceful error when no `graph.db` exists

## Scope Boundaries

**In scope:** New `serve()` entrypoint, simplify `main()`, fix `create_connection` for threading
**Out of scope:** New API endpoints, frontend changes, new dependencies

## Context & Research

### Key Findings (from research swarm)

**Architecture:** `main()` in `__init__.py` is the only entrypoint. It uses argparse to dispatch between MCP (`mcp.run()`) and web (`run_server()`). The web module (`src/cartograph/web/`) is fully implemented with server.py + frontend.py.

**Anti-pattern:** `main()` manually creates `sqlite3.connect()` with `check_same_thread=False` and `row_factory`, bypassing `create_connection()` which provides WAL mode, pragmas, and schema setup. The new `serve()` should use `create_connection()`.

**Impact:** LOW blast radius. No tests reference `--serve`. Tests use `make_handler_class` directly. Only `pyproject.toml` calls `main()`.

**Threading constraint:** `HTTPServer` needs `check_same_thread=False` on the SQLite connection. `create_connection()` doesn't support this — needs a parameter.

## Key Technical Decisions

1. **Add `check_same_thread` param to `create_connection()`** — keeps the factory canonical for all callers
2. **`serve()` gets its own `argparse`** with `prog="kitty-graph"` — clean separation from `main()`
3. **`main()` drops argparse entirely** — it only does `mcp.run(transport="stdio")`, no args needed

## Implementation Units

### Unit 1: Add `check_same_thread` to `create_connection()`

**State:** complete — implemented in 5ad1145

- [ ] **Goal:** Allow web server to use the canonical connection factory
- **Requirements:** R4
- **Dependencies:** None
- **Files:**
  - Modify: `src/cartograph/storage/connection.py`
- **Approach:**
  Add `check_same_thread: bool = True` parameter to `create_connection()`. Pass it through to `sqlite3.connect()`. Default preserves existing behavior.
- **Patterns to follow:** Existing function signature style with type hints
- **Test scenarios:**
  - Happy path: `create_connection(path)` works as before (default `True`)
  - Happy path: `create_connection(path, check_same_thread=False)` creates connection without thread check
- **Verification:** Existing tests pass unchanged

### Unit 2: Create `serve()` entrypoint and simplify `main()`

**State:** complete — implemented in 5ad1145

- [ ] **Goal:** `kitty-graph` command works; `cartographing-kittens` is MCP-only
- **Requirements:** R1, R2, R3, R6
- **Dependencies:** Unit 1
- **Files:**
  - Modify: `src/cartograph/__init__.py`
- **Approach:**
  1. Add `serve()` function with its own argparse (`prog="kitty-graph"`, args: `--port` default 3333, `--project-root` default `.`)
  2. `serve()` validates `graph.db` exists, calls `create_connection(db_path, check_same_thread=False)`, creates `GraphStore`, calls `run_server()` with try/finally cleanup
  3. Simplify `main()` to just import and run `mcp.run(transport="stdio")` — remove argparse, remove `--serve`/`--port`/`--project-root`
  4. Both functions use lazy imports (existing pattern)
- **Patterns to follow:** Lazy imports inside entrypoint functions, try/finally for `store.close()`, `sys.exit(1)` with stderr message for missing db
- **Test scenarios:**
  - Happy path: `serve()` with valid `graph.db` starts the server
  - Edge case: `serve()` with no `graph.db` prints error and exits with code 1
  - Happy path: `main()` starts MCP server (no args needed)
- **Verification:** `kitty-graph --help` shows `--port` and `--project-root`. `cartographing-kittens --help` shows no `--serve` flag.

### Unit 3: Tests

**State:** complete — implemented in 5ad1145

- [ ] **Goal:** Test the new `serve()` error handling and `main()` simplification
- **Requirements:** R1, R3, R6
- **Dependencies:** Unit 2
- **Files:**
  - Modify: `tests/test_web.py`
- **Approach:**
  1. Test `serve()` exits with code 1 and stderr message when `graph.db` is missing (use `tmp_path`)
  2. Test `main()` no longer accepts `--serve` (argparse removed, so it's just a direct MCP launch)
  3. Existing web API tests (`make_handler_class` based) remain unchanged
- **Test scenarios:**
  - Happy path: Existing web API tests still pass
  - Error path: `serve()` with missing db exits gracefully
- **Verification:** `uv run pytest tests/test_web.py` passes

---

## System-Wide Impact

| Area | Impact |
|------|--------|
| `create_connection()` | New optional parameter — backward compatible |
| `main()` | Simplified — removes 30+ lines of argparse/web logic |
| `pyproject.toml` | Already correct — no changes needed |
| Web module | Unchanged — `run_server()` API stays the same |
| Existing tests | No breakage — nothing tests `--serve` flag |

## Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| `check_same_thread=False` changes threading safety | Only used by web server path; matches current behavior |
| Users relying on `cartographing-kittens --serve` | Feature is new/unreleased; `kitty-graph` is the replacement |
| `main()` losing `--project-root` | MCP server doesn't use it (server discovers project root via cwd) |

## Sources & References

- Research: `cartograph-researcher` agent — architecture and dependency analysis
- Patterns: `cartograph-pattern-analyst` agent — `create_connection` is canonical, manual sqlite in `main()` is anti-pattern
- Impact: `cartograph-impact-analyst` agent — LOW risk, 0 test breakage
