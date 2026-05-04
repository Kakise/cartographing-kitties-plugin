---
title: LSP Bridge for Semantic Precision (R2)
type: feat
status: active
date: 2026-05-04
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R2
units:
  - id: 1
    title: LSP client core
    state: pending
  - id: 2
    title: Server registry and lifecycle
    state: pending
  - id: 3
    title: Four MCP tools
    state: pending
  - id: 4
    title: Edge provenance marking (offline)
    state: pending
  - id: 5
    title: Phantom-edge fixture and metric
    state: pending
  - id: 6
    title: Documentation
    state: pending
---

# LSP Bridge — Implementation Plan (R2)

## Overview

Introduce an optional Language Server Protocol client layer so agents can resolve **real**
references, go-to-definition, types, and diagnostics on demand. Tree-sitter remains the bulk-index
primitive; LSP is called per-query for precision and for verifying heuristic `calls` / `inherits`
edges. Exposes four new MCP tools. Ship with pyright (Python) and
`typescript-language-server` (TS/JS) as the initial targets — note that bare `tsserver` speaks
TypeScript's own JSON-RPC protocol, not LSP; the LSP wrapper is a separate npm package.
Additional servers light up automatically as R3 lands languages.

## Problem Frame

Tree-sitter extraction currently derives `calls` and `inherits` heuristically: it matches by
*name*, not *resolved symbol*. This creates phantom edges (two unrelated methods named `run`
collapse), and it cannot answer cross-file reference queries without grep fallbacks. 2026
research shows LSP wrappers reduce hallucinated APIs ~27% and mislocalized edits ~33%.

The goal is **additive** — not to re-derive the whole graph from LSP (slow, per-language setup
cost), but to give agents a precise-on-demand escape hatch and a post-edit diagnostic loop.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R2.a — LSP client layer under `src/cartograph/lsp/` | Unit 1 |
| R2.b — `find_references` tool | Unit 3 |
| R2.c — `goto_definition` tool | Unit 3 |
| R2.d — `get_type` tool | Unit 3 |
| R2.e — `get_diagnostics` tool (post-edit feedback) | Unit 3 |
| R2.f — LSP-verified edge provenance in graph | Unit 4 |
| R2.g — Measurable drop in phantom call edges on a fixture corpus | Unit 5 |

## Scope Boundaries

- **In scope:** LSP client lifecycle, four new MCP tools, per-language server bootstrapping for
  pyright + tsserver, edge-provenance flag in `properties` JSON, fixture-based measurement harness.
- **Out of scope:** rewriting the AST extraction pipeline; LSP-based annotation generation; managing
  the user's IDE LSP — Cartograph spawns its own dedicated server instances.

## Memory Context

Treat-box and litter-box queries (graph DB at `.pawprints/graph.db`, keywords: `embed`, `hybrid`,
`search`, `lsp`, `pyright`, `rrf`, `vec`, `language server`, `reference`, `sqlite`) returned no
topic-specific entries for LSP, pyright, JSON-RPC framing, or phantom-edge verification as of
2026-05-04. The treat box currently holds only general process conventions (the plan-state
`**State:**` standalone-paragraph rule and the `AskUserQuestion` skills protocol). The litter
box is empty. No prior failures or anti-patterns constrain this plan. Proceed using the
predecessor's technical decisions verbatim; record any LSP-process leak, pyright version-skew,
or JSON-RPC framing lessons during execution so subsequent refreshes inherit them.

## Context & Research

### Annotation Status

946 annotated nodes. No new node kinds needed — LSP outputs map to existing `function`, `method`,
`class`, etc.

### Target Files (all new unless marked)

- `src/cartograph/lsp/__init__.py` — new module.
- `src/cartograph/lsp/client.py` — JSON-RPC-over-stdio LSP client.
- `src/cartograph/lsp/lifecycle.py` — server spawn / warm-up / shutdown.
- `src/cartograph/lsp/servers.py` — per-language server config (pyright,
  typescript-language-server).
- `src/cartograph/server/tools/lsp.py` — four MCP tools.
- `src/cartograph/server/main.py` — register `tools.lsp` (modify).
- `src/cartograph/storage/migrations/0007_lsp_provenance.sql` — optional migration if we
  materialize provenance as a column; see Decision below.
- `tests/test_lsp_bridge.py` — new.
- `tests/fixtures/lsp_corpus/` — new small repos exercising cross-file refs, overrides,
  overloaded names.

### Key Symbols

- `src/cartograph/server/main.py::lifespan` — current server bootstrap; this is where LSP
  processes get spawned lazily on first request and shut down on server exit.
- `cartograph.server.tools.query::search` — unaffected; LSP is a separate tool surface.

## Key Technical Decisions

### Lifecycle ownership: **Cartograph spawns and manages** its own LSP processes

Brainstorm open question resolved. Rationale:
- Portable to CI (the brainstorm's stated priority).
- Self-contained: no assumption an IDE is running.
- Lazy: servers only spawn on first LSP tool call, not at MCP server startup.
- Singleton per language: one pyright, one typescript-language-server for the lifetime of the
  MCP server process.

Trade-off accepted: a slower cold start on first LSP call (pyright ~2 s to warm up on this repo).
Subsequent calls are sub-100 ms.

### Client implementation: `pygls`-style manual client, not `pygls` itself

`pygls` is a **server** framework; there's no first-party Python LSP client library.
Recommended: write a minimal JSON-RPC-over-stdio client in `client.py` (≈200 lines). We need only
`initialize`, `textDocument/didOpen`, `textDocument/references`, `textDocument/definition`,
`textDocument/hover`, `textDocument/publishDiagnostics`. Avoid dragging in a large client
dependency we'd have to maintain around.

### Server inventory (initial)

| Language | Server | Install | Detected via |
|---|---|---|---|
| Python | pyright | `nodeenv` or system `node`; `npm install -g pyright` | `pyright --version` |
| TypeScript / JS / TSX | typescript-language-server | `npm install -g typescript typescript-language-server` | `typescript-language-server --version` |

R3 languages (Go, Rust, Java) plug in later via the same `servers.py` registry without touching
the client or tool code.

### Discovery

- Check `$PATH` for each binary at lazy-init time.
- If missing, the specific tool returns `{"error": "pyright not found", "install_hint": "npm i -g pyright"}`.
  Other tools and other languages remain functional. No hard startup failure.

### Provenance storage: **edge `properties` JSON**, no new column

Adding a column means a migration *and* it bloats every row. Instead, when we verify a `calls` or
`inherits` edge via LSP (see Unit 4), write `properties = json({"verified_by_lsp": true,
"verified_at": "...", "lsp_server": "pyright"})`. Keeps the schema stable.

### MCP tool signatures

```
find_references(qualified_name: str) -> list[{file_path, line, column, snippet}]
goto_definition(qualified_name: str) -> {file_path, line, column}
get_type(file_path: str, line: int, column: int) -> {type_string, documentation}
get_diagnostics(file_paths: list[str]) -> {file_path: [{severity, line, message, source}]}
```

All four accept `qualified_name` or `(file_path, line, column)` where the LSP contract requires
coordinates; `qualified_name`-taking tools internally resolve position via `GraphStore.get_node_by_name`.

## Open Questions

### Resolve Before Implementing

- **What is the "initialize" root for the LSP server?** The current project CWD. OK for v1.
  Monorepo support (multiple workspaces) is v2 — explicit non-goal.
- **Do we open every file eagerly or only ones referenced in tool calls?**
  Recommendation: lazy `didOpen` per file, cached. Minimizes startup cost; pyright handles
  cross-file resolution on demand. Decision needed before Unit 2.

### Defer

- Per-language config customization (`pyright.ini`, `tsconfig.json` overrides). Respect whatever
  exists in the project root; expose no Cartograph-side override for v1.

## Implementation Units

### Unit 1 — LSP client core

**State:** pending

- [ ] `src/cartograph/lsp/client.py` — `LspClient` class with methods for `initialize`,
      `shutdown`, `send_request`, `send_notification`, and `recv`. Uses
      `subprocess.Popen(..., stdin=PIPE, stdout=PIPE, stderr=PIPE)` and framed JSON-RPC
      (Content-Length headers).
- [ ] Thread pumping stderr → logger, stdout → response queue. Request/response correlation by
      JSON-RPC `id`.
- [ ] Unit tests mock the subprocess with an echo server that verifies framing and correlation.

**Files:** `src/cartograph/lsp/__init__.py`, `src/cartograph/lsp/client.py`,
`tests/test_lsp_client.py`.

**Test scenarios:**
- Happy: send `initialize` → receive `InitializeResult`.
- Edge: two concurrent requests interleave correctly (IDs preserved).
- Error: subprocess dies mid-session → `LspConnectionError` raised, client marked dead.

### Unit 2 — Server registry and lifecycle

**State:** pending

- [ ] `src/cartograph/lsp/servers.py` — `SERVER_CONFIGS: dict[Language, ServerConfig]`, initially
      `{"python": ServerConfig(cmd=["pyright-langserver", "--stdio"], ...),
      "typescript": ServerConfig(cmd=["typescript-language-server", "--stdio"], ...)}`.
- [ ] `src/cartograph/lsp/lifecycle.py` — `get_server(language: str) -> LspClient` with lazy
      init + caching. `shutdown_all()` for `lifespan` teardown.
- [ ] In `server/main.py::lifespan`, wire `shutdown_all()` into the server-stop hook.
- [ ] Files are opened lazily via `didOpen` on first tool call per file; `didChange` is not used
      (we spawn fresh servers per session; no live editing).

**Files:** `src/cartograph/lsp/servers.py`, `src/cartograph/lsp/lifecycle.py`,
`src/cartograph/server/main.py` (modify).

**Test scenarios:**
- Happy: first call to `get_server("python")` spawns pyright; second call returns cached.
- Edge: pyright binary missing → `get_server` raises `ServerUnavailable` with install hint.
- Edge: server hangs >10 s on init → timeout, error propagated.

### Unit 3 — Four MCP tools

**State:** pending

- [ ] `src/cartograph/server/tools/lsp.py` — four tool functions with FastMCP decorators.
      Each tool:
      1. Resolves qualified name → (file_path, line, column) via `GraphStore.get_node_by_name`.
      2. Calls `get_server(language)`.
      3. Issues LSP request.
      4. Translates LSP response → Cartograph-shaped dict.
      5. On server unavailability, returns `{"error": "...", "install_hint": "..."}` — does
         **not** raise (MCP tools should degrade gracefully).
- [ ] Register in `server/main.py`.

**Files:** `src/cartograph/server/tools/lsp.py`, `src/cartograph/server/main.py` (modify).

**Test scenarios per tool:**
- `find_references`: happy path on multi-file fixture; returns ≥1 ref. Edge: unknown symbol →
  empty list, not error.
- `goto_definition`: happy on fixture with interface + impl; edge: stdlib symbol returns
  `library` pseudo-path (graceful, no crash).
- `get_type`: happy returns type string; edge: position without a symbol → `{"type_string":
  null}`.
- `get_diagnostics`: happy returns empty list on a clean file; edge: syntax error file returns
  ≥1 diagnostic with severity 1.

### Unit 4 — Edge provenance marking (offline)

**State:** pending

- [ ] Add `src/cartograph/lsp/verify_edges.py` — script that walks ambiguous `calls`/`inherits`
      edges (edges where the target has ≥2 candidate nodes by name), asks LSP for the real
      referent, and updates the edge's `properties` JSON with `verified_by_lsp=true` and
      `resolved_target_id=<id>` where divergent.
- [ ] Expose as `uv run python -m cartograph.lsp.verify_edges`. Ship as opt-in; **not run
      automatically** during indexing (too slow for bulk). Document in README.

**Files:** `src/cartograph/lsp/verify_edges.py` (new).

**Test scenarios:**
- Happy: fixture with two unrelated `run` methods; script relinks call edges to the correct one.
- Edge: symbol not found by LSP → edge marked `verified_by_lsp=true, resolution="unknown"`.

### Unit 5 — Phantom-edge fixture and metric

**State:** pending

- [ ] `tests/fixtures/lsp_corpus/` — small repo with ≥3 known phantom-edge cases (ambiguous names,
      overrides, overloaded methods).
- [ ] `tests/test_lsp_phantom_reduction.py` — asserts phantom-edge count **before** LSP
      verification ≥ N, and **after** ≤ M where N−M ≥ 50% reduction on the fixture.

**Test scenarios:**
- Asserts measurable reduction; failure = R2 does not meet its success criterion.

### Unit 6 — Documentation

**State:** pending

- [ ] Update `README.md` with LSP-bridge section (install hints per language).
- [ ] Update `CLAUDE.md` to list the four new MCP tools.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md`.
- [ ] Note in `plugins/kitty/skills/kitty-impact/SKILL.md` that `find_references` is the
      precision-grade alternative to `find_dependents` for call-verification workflows.

**Files:** `README.md`, `CLAUDE.md`,
`plugins/kitty/skills/kitty/references/tool-reference.md` (modify),
`plugins/kitty/skills/kitty-impact/SKILL.md` (modify).

## System-Wide Impact

- **Plugin surface:** +4 MCP tools (13 → 17 after R2 alone).
- **Cold start:** first LSP tool call adds 1–3 s (language server spawn). Subsequent calls
  sub-100 ms. No impact on tools that don't touch LSP.
- **Install surface:** optional `pyright` (Node) and `tsserver` (Node). Base Cartograph install
  unchanged. Missing tools return helpful error messages per tool, not global failure.
- **Agents:** `expert-kitten-correctness` and `expert-kitten-impact` can now call
  `find_references` / `get_diagnostics` for precision. Update their prompts in Unit 6.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| LSP server process leaks on test failure | `pytest` finalizer calls `shutdown_all()`; fixture uses `yield` pattern |
| pyright output schema varies between versions | Pin `pyright>=1.1.400` in docs; pytest fixture runs `pyright --version` check |
| Server startup blocks the whole MCP server event loop | Spawn in a background thread; mark server `ready` when `initialized` response arrives |
| Using bare `tsserver` instead of the LSP wrapper misaligns the protocol | Use `typescript-language-server` (LSP wrapper). Document in README; install hint is explicit |

**Dependencies:** none on other roadmap plans. R3 language additions light up new server entries
in `servers.py` but don't change the client.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R2)
- Predecessor plan (refresh source): `docs/plans/2026-04-23-003-feat-lsp-bridge-plan.md`
- LSP spec: https://microsoft.github.io/language-server-protocol/
- LSAP framing: https://github.com/lsp-client/LSAP

## Handoff

Ready for `kitty:work`. Entry point: Unit 1. Units 1–3 must land sequentially; Unit 4 is
independent but exercises Unit 3; Unit 5 is the exit gate.
