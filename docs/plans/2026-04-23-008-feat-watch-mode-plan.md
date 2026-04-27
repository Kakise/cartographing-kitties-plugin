---
title: Watch Mode / Live Graph Subscription (R7)
type: feat
status: active
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
parent: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
requirement: R7
---

# Watch Mode — Implementation Plan (R7)

## Overview

Re-index on file save (sub-second for single-file changes) and stream `graph_diff` deltas to
subscribed agents via a new MCP tool `subscribe_graph_changes`. Builds directly on the existing
`graph_diff` / `validate_graph` infrastructure in `server/tools/reactive.py`. Enables agents to
react to their own edits without polling.

## Problem Frame

Agents that edit code today have to re-run `index_codebase` then `graph_diff` to see structural
consequences. That's a polling pattern. A filesystem watcher plus a subscription stream makes it
push-based — closer to the Cursor-style live-indexing experience and enabling post-edit loops
like R2's `get_diagnostics`.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R7.a — Filesystem watcher re-indexes on save | Unit 1 |
| R7.b — Debounced + coalesced event processing | Unit 2 |
| R7.c — `subscribe_graph_changes` MCP tool streaming `graph_diff` deltas | Unit 3 |
| R7.d — Sub-second re-index latency for single-file changes | Unit 4 (benchmark gate) |

## Scope Boundaries

- **In scope:** `watchdog`-based observer, debounce/coalesce logic, SSE / streaming MCP response,
  integration with existing `graph_diff`, tests with a mock filesystem.
- **Out of scope:** multi-process coordination (single-server assumption); Windows-specific
  quirks beyond what `watchdog` handles; network filesystems; persistent subscription across
  server restarts.

## Context & Research

### Extension Points

- `src/cartograph/server/tools/reactive.py::graph_diff` — already returns the diff between
  snapshots. R7 wraps this in a streaming tool.
- `src/cartograph/indexing/indexer.py::index_changed` — already incremental. R7 calls it with a
  one-file changeset per event.
- `src/cartograph/indexing/discovery.py::detect_changes` — already handles git-diff + hash
  fallback. R7 passes a pre-known file list directly, bypassing directory walk for speed.
- `src/cartograph/server/main.py::lifespan` — watcher starts/stops here.

### MCP Streaming Caveat

MCP 2024-11 does not define a first-class server-push subscription primitive; tool calls are
request/response. Three viable deliveries, ranked:

1. **Long-poll tool (recommended for v1).** `subscribe_graph_changes(since_version: int, timeout:
   int = 30) -> list[DiffEvent]` returns buffered events since `since_version` (or blocks up to
   `timeout` seconds for the next one). Agents loop the call. Simple, fits the protocol, works
   today. The tool queues events in-memory keyed on `graph_version`.
2. **Progress notifications.** FastMCP supports `ctx.report_progress()` for long-running tools;
   we could keep one call open and send progress events as diffs. Works but semantically misuses
   progress.
3. **True SSE.** Possible with custom transport, but breaks the stdio-only assumption.

This plan uses option 1. Revisit once MCP spec standardizes subscriptions.

## Key Technical Decisions

### Library: `watchdog>=4.0.0`

- Cross-platform (Linux inotify, macOS FSEvents, Windows ReadDirectoryChangesW).
- Mature, small API.
- Added to `pyproject.toml` as a core dependency (not optional — watch mode ships on).

### Debounce + coalesce

- 500 ms debounce per path.
- Burst coalesce: events within the debounce window stack; the indexer runs once with all
  affected files.
- Rename events: delete old path node set + index new path.

### Watcher scope

- Watches only paths matching the existing `discover_files` filter (extensions + gitignore). No
  need to watch everything.
- Startup cost: one directory-walk pass to register watches. Amortized over many events.

### Subscription delivery

- Server keeps a set of active subscribers (asyncio queues).
- After each re-index, compute `graph_diff` between snapshots taken *before* and *after* the
  index run. Push the diff object onto every subscriber queue.
- On slow consumers, drop oldest and log a warning (avoid unbounded memory).

## Open Questions

### Resolve Before Implementing

- **Should watch mode be on by default, or opt-in via env var / flag?** Recommend: opt-in via
  `KITTY_WATCH_MODE=true` env var for v1. Reason: watcher adds file descriptors and a background
  thread; some users will run Cartograph in CI where that's pointless. Flip default after ship
  if adoption is smooth.
- **What's in the diff payload streamed to subscribers?** Recommend: same shape as
  `graph_diff` returns today, plus a `timestamp` and `changed_files: list[str]`. Agents can
  cheaply ignore deltas irrelevant to their focus.

### Defer

- Harness-level implementation (per brainstorm deferral). Revisit once Claude Code hooks system
  is stable enough to push events — until then, owning the watcher inside Cartograph is the
  cleaner default.

## Implementation Units

### Unit 1 — Filesystem watcher

- [ ] Add `watchdog>=4.0.0` to `pyproject.toml`.
- [ ] `src/cartograph/indexing/watcher.py` — `FileWatcher` class wrapping
      `watchdog.observers.Observer` + `watchdog.events.FileSystemEventHandler`. Emits
      `(path, event_type)` onto an asyncio queue.
- [ ] Filter events using the existing `discover_files` matcher to drop out-of-scope paths.

**Files:** `src/cartograph/indexing/watcher.py` (new).

**Test scenarios:**
- Happy: writing `.py` file → event emitted.
- Edge: writing to `.pawprints/graph.db` → filtered out.
- Edge: `.gitignore`-ignored path → filtered out.

### Unit 2 — Debounce + coalesce

- [ ] `src/cartograph/indexing/watcher.py::Debouncer` — collects events for 500 ms, emits a
      deduped set of (path, event_type).
- [ ] `WatchModeCoordinator.run()` — async loop: await debounced batch → call
      `Indexer.index_changed(paths=batch)` → compute `graph_diff` → fan out to subscribers.

**Test scenarios:**
- Happy: 5 saves of the same file within 500 ms → 1 re-index call.
- Happy: 5 saves of 5 different files within 500 ms → 1 re-index call with 5 files.
- Edge: save + rename → old path's nodes deleted, new path indexed.

### Unit 3 — `subscribe_graph_changes` MCP tool (long-poll)

- [ ] `src/cartograph/server/tools/reactive.py::subscribe_graph_changes(since_version: int = 0,
      timeout_s: int = 30) -> {events: list[DiffEvent], next_since_version: int}`:
      1. If buffered events for `graph_version > since_version` exist, return immediately.
      2. Otherwise `await` the coordinator's "new diff" asyncio event with the given timeout.
      3. On timeout, return `{events: [], next_since_version: since_version}` so the agent can
         loop.
- [ ] Maintain a rolling buffer of last 100 diff events keyed by `graph_version` in the
      coordinator. Events older than the oldest `since_version` any caller has seen get evicted.
- [ ] Wire `WatchModeCoordinator` startup/shutdown into `server/main.py::lifespan`. Only
      start if `KITTY_WATCH_MODE=true`.
- [ ] If watch mode is disabled, `subscribe_graph_changes` returns `{error: "...", hint: "set
      KITTY_WATCH_MODE=true", events: []}` immediately. Agents get a clear signal.

**Files:** `src/cartograph/server/tools/reactive.py` (modify),
`src/cartograph/server/main.py` (modify).

**Test scenarios:**
- Happy: poll with `since_version=N`, wait, modify file, next poll returns the diff and
  `next_since_version = N+1`.
- Happy: two concurrent pollers both see the same events in the buffer.
- Edge: timeout path returns empty events and unchanged `since_version`; caller loops.
- Edge: watch mode disabled → call returns immediately with the error hint, no polling loop
  wastes cycles.

### Unit 4 — Latency benchmark

- [ ] `tests/test_watch_mode.py::test_single_file_reindex_under_one_second`: modify a fixture
      file, wait for the diff event, assert total latency (save → diff received) < 1000 ms p95.
- [ ] `tests/test_watch_mode.py::test_burst_coalesce`: write 10 files in 200 ms, assert exactly
      one re-index run fires.

### Unit 5 — Documentation

- [ ] Update `README.md` with Watch Mode section (env var, use case).
- [ ] Update `CLAUDE.md` tool list.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md`.
- [ ] Update `plugins/kitty/skills/kitty-work/SKILL.md` to note that workers can subscribe to
      pick up their own edits for post-edit validation (synergy with R2's `get_diagnostics`).

## System-Wide Impact

- **Plugin surface:** +1 MCP tool (streaming).
- **Dependencies:** +1 (`watchdog`).
- **Runtime:** 1 background thread (watchdog observer) + 1 asyncio task (coordinator) when watch
  mode is enabled.
- **Memory:** subscriber queues are bounded (drop-oldest at 100 pending events).

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Filesystem events fire spuriously (editors write temp files) | Filter with existing gitignore matcher; 500 ms debounce collapses bursts |
| Watcher fails to install on exotic platforms | Detect `watchdog.observers.Observer` load failure, log, disable watch mode — rest of server still functions |
| Subscribers hold connections forever | Each tool call has an upstream MCP timeout; our generator respects cancellation |
| Network filesystems give incorrect events | Document unsupported; fall back to polling via `index_changed` manual call |

**Dependencies:** none. Synergizes with **R2** (agents can call `get_diagnostics` after receiving
a watch-mode diff) but doesn't require it.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R7)
- Parent roadmap: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
- watchdog docs: https://python-watchdog.readthedocs.io/
- Existing reactive infrastructure: `docs/plans/2026-03-28-006-feat-graph-reactive-engineering-plan.md`

## Handoff

Ready for `kitty:work`. Entry point: Unit 1. Units 2–3 build on it sequentially. Unit 4
(benchmark) is the exit gate: must hit <1 s p95.
