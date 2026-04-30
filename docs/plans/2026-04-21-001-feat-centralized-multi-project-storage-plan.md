---
title: Centralized Multi-Project Storage Plan
type: feat
status: complete
date: 2026-04-21
origin: direct-request
implemented_in: d82e416
---

## Overview

Add multi-project storage support by separating the **source project root** from the **storage root**. The target model for this plan is a centralized directory that contains one isolated Cartograph data directory per indexed project, rather than a single SQLite file shared by all projects.

This preserves the current runtime model of `project_root -> GraphStore` while allowing users to keep graph databases outside the repository checkout.

## Problem Frame

Today the server and web entrypoints derive storage from the project root and assume the graph lives at `.pawprints/graph.db` inside the repository. That assumption is encoded in path-resolution helpers, entrypoints, plugin manifests, docs, and memory export paths.

That design makes local setup simple, but it prevents:

- centralizing graph storage in a dedicated folder
- reusing the same machine-wide storage root across many projects
- keeping repositories free from generated graph state

The important architectural constraint is that the current schema and `GraphStore` APIs are **not project-scoped**. `qualified_name` is globally unique and graph metadata is global per database, so true multi-project support inside one shared SQLite file would require a broader storage redesign.

## Requirements Trace

- R1. Support a configurable centralized storage root independent of the source project root.
- R2. Preserve backward compatibility with the existing `.pawprints/`-in-project layout by default.
- R3. Keep one project’s graph, migration state, and memory artifacts isolated from other projects.
- R4. Expose the new storage configuration consistently through MCP startup, web CLI, and plugin manifests.
- R5. Preserve incremental indexing semantics by continuing to index relative to the source project root.
- R6. Keep migration behavior clear for existing `.cartograph/` and `.pawprints/` directories.
- R7. Update tests and docs so the new storage model is explicit and verifiable.

## Scope Boundaries

In scope:

- centralized storage root configuration
- stable per-project storage directory derivation
- path helper refactor
- server, CLI, plugin, and docs updates
- optional centralization of markdown memory exports
- regression coverage for old and new layouts

Out of scope:

- storing multiple projects in one shared `graph.db`
- project-scoped schema changes such as `project_id` on `nodes`
- cross-project search or graph traversal
- migration of existing databases into a single consolidated SQLite file

## Context & Research

### Annotation Status

- Total nodes: 899
- Annotated: 692 (76.97%)
- Pending: 207
- Failed: 0

### Relevant Files And Current Responsibilities

- `src/cartograph/compat.py`
  Current root and data-dir resolution. `resolve_project_root()` reads `KITTY_PROJECT_ROOT` / `CARTOGRAPH_PROJECT_ROOT`. `resolve_db_dir(project_root)` currently returns `<project_root>/.pawprints`, auto-migrating from `.cartograph`.

- `src/cartograph/server/main.py`
  MCP startup path. `lifespan()` resolves project root, then resolves DB dir, then opens `<db_dir>/graph.db`.

- `src/cartograph/__init__.py`
  Public web CLI entrypoint. `serve()` accepts `--project-root` and then looks for `resolve_db_dir(args.project_root) / "graph.db"`.

- `src/cartograph/web/main.py`
  Secondary web entrypoint with the same assumption as above.

- `src/cartograph/server/tools/memory.py`
  Memory tools export markdown to `root / ".pawprints" / "litter-box.md"` and `root / ".pawprints" / "treat-box.md"`, so they currently ignore any alternate DB location.

- `src/cartograph/storage/graph_store.py`
  Storage APIs are unscoped by project. Node identity is based on globally unique `qualified_name`. `graph_meta` holds one global graph version counter per database.

- `src/cartograph/storage/migrations/0001_baseline.sql`
  `nodes.qualified_name` is globally `UNIQUE`, confirming that a single shared DB would need schema work.

- `plugins/kitty/.mcp.json`
- `plugins/kitty/.claude-plugin/plugin.json`
- `plugins/kitty/gemini-extension.json`
  Plugin startup currently injects only `KITTY_PROJECT_ROOT`.

### Key Relationships

- `cartograph.server.main::lifespan` calls:
  - `cartograph.compat::resolve_project_root`
  - `cartograph.compat::resolve_db_dir`

- `cartograph.compat::resolve_db_dir` sits on the startup path for MCP initialization and indirectly affects all tool modules through shared server state.

- `cartograph.server.tools.memory` imports `cartograph.server.main`, so memory export behavior is coupled to the same global startup context.

### Design Constraint From Storage Layer

The current schema is compatible with:

- one project per database
- many databases under one parent folder

The current schema is not compatible with:

- many projects inside one SQLite database without adding project scoping to storage and queries

## Key Technical Decisions

### 1. Introduce explicit storage-path resolution, not just DB-dir resolution

Replace the current narrow helper with a richer path resolver in `src/cartograph/compat.py`, for example:

- `resolve_project_root() -> Path`
- `resolve_storage_root(project_root: Path, storage_root: str | Path | None = None) -> Path`
- `derive_project_storage_dir(project_root: Path, storage_root: Path) -> Path`
- `resolve_storage_paths(...) -> StoragePaths`

`StoragePaths` should include at least:

- `project_root`
- `storage_root`
- `data_dir`
- `db_path`
- `treat_box_path`
- `litter_box_path`

Reasoning:

- the codebase now has more than one storage artifact
- memory exports and DB path should be derived from the same source of truth
- a structured return value reduces repeated path assembly in entrypoints and tools

### 2. Keep project identity filesystem-derived, but define path-move behavior explicitly

Under a centralized storage root, derive a deterministic per-project directory such as:

- `<storage_root>/<slugified-project-name>-<short-hash>/`

Where the hash is based on the normalized resolved absolute project root path.

Reasoning:

- avoids collisions between projects with the same leaf directory name
- keeps paths human-readable
- does not require persistent registry state

Required follow-up behavior:

- treat a changed resolved project path as a **new storage identity by default**
- detect and document that moving or renaming a checkout will create a new per-project storage directory unless the user manually migrates or pins storage more explicitly in a future enhancement
- add a migration/discovery note in docs so this is an intentional tradeoff, not a silent surprise

Reasoning:

- the current system has no project registry or persistent canonical project ID
- trying to guess that two different absolute paths are “the same project” would create ambiguous and risky merge behavior
- explicit “new path, new storage identity” semantics are safer for the first version than heuristic DB reuse

### 3. Default to the current local layout when no centralized root is configured

If no centralized storage root is provided, preserve current behavior:

- use `<project_root>/.pawprints/`
- continue legacy `.cartograph -> .pawprints` migration in that local mode

Reasoning:

- minimizes upgrade risk
- keeps current users and tests stable
- avoids surprising storage moves on upgrade

### 4. Add a new top-level configuration input for centralized storage

Support a dedicated storage env var and matching CLI flag:

- env: `KITTY_STORAGE_ROOT`
- fallback env for compatibility if desired: `CARTOGRAPH_STORAGE_ROOT`
- web CLI flag: `--storage-root`

Do not overload `KITTY_PROJECT_ROOT` for storage purposes.

Reasoning:

- project root and storage root are different concepts
- explicit configuration keeps the indexer contract unchanged
- packaged clients need a documented way to pass this value without patching plugin files ad hoc

### 5. Centralize memory exports with the DB when centralized storage is enabled

When `KITTY_STORAGE_ROOT` or `--storage-root` is set, export markdown files beside the DB in the per-project data directory.

Paths:

- `<data_dir>/treat-box.md`
- `<data_dir>/litter-box.md`

Reasoning:

- keeps all generated artifacts together
- avoids split-brain behavior where DB is centralized but exports still appear in the repo
- matches the mental model of “all Cartograph state lives under the storage root”

### 6. Do not implement a single shared DB in this feature

Document it as a future alternative requiring:

- `projects` table
- `project_id` on graph and memory tables
- `UNIQUE(project_id, qualified_name)`
- project-scoped `graph_meta`
- project-scoped query methods throughout `GraphStore`

Reasoning:

- this is a schema and API redesign, not a configuration enhancement
- mixing it into this feature would enlarge migration risk significantly

## Open Questions

- Should the centralized storage feature also support an explicit `KITTY_DB_PATH` override for advanced users, or is `KITTY_STORAGE_ROOT` sufficient?
- Should plugin manifests expose `KITTY_STORAGE_ROOT` through a documented user-editable env field, or should centralized storage remain CLI/server-env only in the first release?
- Should legacy `.cartograph -> .pawprints` migration happen only in local mode, or also when a centralized root points at an old central `.cartograph` directory layout?

These questions do not block the basic implementation. The plan below assumes:

- `KITTY_STORAGE_ROOT` is the primary supported override
- plugins expose centralized storage as an explicit opt-in configuration surface, not as an always-on default
- legacy migration remains local-layout focused unless a concrete central legacy layout already exists

## Implementation Units

- [ ] U1. Introduce unified storage path resolution
  Goal: Create one authoritative place to derive project root, storage root, per-project data dir, DB path, and memory export paths.
  Requirements: R1, R2, R3, R6
  Dependencies: None
  Files:
  - `src/cartograph/compat.py`
  - `tests/` new or updated compat-focused coverage in the nearest existing test module
  Approach:
  - Add a small `StoragePaths` dataclass or equivalent typed container.
  - Preserve current default local layout.
  - If centralized storage is configured, compute a stable per-project directory under the storage root.
  - Keep `.cartograph -> .pawprints` migration behavior for the default local layout.
  Patterns to follow:
  - Keep migration and compatibility logic localized in `compat.py`.
  - Prefer explicit path objects over reassembling strings throughout call sites.
  Test scenarios:
  - Happy path: no storage override -> returns `<project_root>/.pawprints/graph.db`
  - Happy path: centralized root configured -> returns `<storage_root>/<project-key>/graph.db`
  - Edge case: two different project roots with same basename -> distinct per-project dirs
  - Migration path: existing local `.cartograph/` -> migrated to local `.pawprints/`
  - Error path: invalid or non-creatable centralized root -> surfaces a clear exception
  Verification:
  - Unit tests cover both local and centralized resolution paths

- [ ] U2. Rewire startup and web entrypoints to use the new storage contract
  Goal: Make MCP startup and web explorer use unified storage resolution.
  Requirements: R1, R2, R4, R5
  Dependencies: U1
  Files:
  - `src/cartograph/server/main.py`
  - `src/cartograph/__init__.py`
  - `src/cartograph/web/main.py`
  - `tests/test_web.py`
  - `tests/test_stdio_e2e.py`
  Approach:
  - Resolve a `StoragePaths` object once at startup.
  - Keep `_root` bound to the source project root so indexing and annotation path resolution continue to work.
  - Open `storage_paths.db_path` instead of reconstructing `<db_dir>/graph.db`.
  - Extend web CLIs with `--storage-root`.
  Patterns to follow:
  - Preserve existing startup shape and shared module-level state.
  - Add configuration without changing indexing semantics.
  Test scenarios:
  - Happy path: MCP server indexes a project with centralized storage enabled
  - Happy path: web CLI opens centralized DB successfully
  - Edge case: web CLI with project root and storage root set but missing DB -> same clear error semantics
  - Integration: stdio E2E continues to work with local mode and with centralized mode
  Verification:
  - `tests/test_stdio_e2e.py` and `tests/test_web.py` cover both path modes

- [ ] U3. Move memory exports onto resolved storage paths
  Goal: Ensure non-DB artifacts follow the same storage layout as the database.
  Requirements: R1, R3, R4, R7
  Dependencies: U1
  Files:
  - `src/cartograph/server/main.py`
  - `src/cartograph/server/tools/memory.py`
  - `tests/test_memory.py`
  - `tests/test_server.py`
  Approach:
  - Store resolved storage paths in shared server state, not only `_root`.
  - Update memory tools to export markdown via resolved `treat_box_path` and `litter_box_path`.
  - Keep query behavior unchanged since entries still live in the same project-specific DB.
  Patterns to follow:
  - Derive artifact paths from startup state, not from ad hoc path concatenation.
  Test scenarios:
  - Happy path: centralized mode writes markdown next to centralized DB
  - Happy path: local mode still writes under local `.pawprints/`
  - Integration: adding a treat/litter entry updates both DB and markdown export in the expected location
  Verification:
  - Server and memory tests assert export destinations for both layouts

- [ ] U4. Expose centralized storage in plugin manifests and docs
  Goal: Make the new feature discoverable without breaking existing plugin usage.
  Requirements: R4, R7
  Dependencies: U2
  Files:
  - `plugins/kitty/.mcp.json`
  - `plugins/kitty/.claude-plugin/plugin.json`
  - `plugins/kitty/gemini-extension.json`
  - `README.md`
  - `CLAUDE.md`
  - `GEMINI.md`
  Approach:
  - Document `KITTY_STORAGE_ROOT` and the resulting path layout.
  - Keep plugin defaults unchanged for backward compatibility, but update packaged plugin manifests and/or adjacent packaging docs so users have a documented env slot to set `KITTY_STORAGE_ROOT` without modifying Python source.
  - If a manifest cannot express a user-editable override directly, document centralized storage as supported via external environment injection for plugin hosts and via CLI flags for local runs.
  - Update all docs that currently claim the graph always lives in-project.
  Patterns to follow:
  - Keep default plugin config simple and backward compatible.
  - Treat centralized storage as an additive capability, not a mandatory behavior change.
  Test scenarios:
  - Happy path: documented config matches actual startup behavior
  - Happy path: a packaged plugin config can pass `KITTY_STORAGE_ROOT` without editing library code
  - Regression: docs no longer claim `.pawprints/graph.db` is always in project root
  Verification:
  - User-facing docs and plugin examples are internally consistent

- [ ] U5. Add regression coverage for project isolation under one storage root
  Goal: Prove that multiple projects can share one storage root without collisions.
  Requirements: R1, R3, R5, R7
  Dependencies: U1, U2, U3
  Files:
  - `tests/test_stdio_e2e.py`
  - `tests/test_server.py`
  - `tests/test_web.py`
  - potentially a new focused test module if isolation scenarios become noisy
  Approach:
  - Create two temporary project fixtures with overlapping file names or qualified names.
  - Point both at the same centralized storage root.
  - Verify each project resolves to a distinct per-project data directory and isolated DB.
  Patterns to follow:
  - Prefer E2E tests for startup/config behavior.
  - Keep schema untouched; prove isolation through filesystem layout.
  Test scenarios:
  - Happy path: two projects under one storage root each create their own DB
  - Edge case: same directory basename but different absolute roots -> no collision
  - Edge case: moving the same project to a different absolute path yields a new storage directory and is documented as such
  - Integration: indexing one project does not affect search or node counts in the other project’s DB
  Verification:
  - Cross-project isolation tests fail under a naive single-dir implementation and pass with per-project storage keys

## System-Wide Impact

- Compatibility layer becomes the canonical source of storage configuration.
- MCP startup gains a storage concept distinct from the source project root.
- Web CLI surface expands with a new `--storage-root` argument.
- Memory export behavior becomes consistent with DB placement.
- Plugin and documentation language must change from “the graph is stored in `.pawprints/graph.db` in the project root” to “by default it is stored there; optionally it can live under a centralized storage root.”

## Risks & Dependencies

- Risk: path derivation collisions if project identity is based only on folder name.
  Mitigation: include a short hash of resolved absolute project path.

- Risk: path-based identity causes a moved or renamed checkout to miss its previous DB and memory exports.
  Mitigation: define this explicitly as first-version behavior, document it, and leave stable project IDs or explicit DB pinning as a future enhancement.

- Risk: hidden behavior change if centralized mode silently moves user data.
  Mitigation: keep the old layout as the default and require explicit opt-in for centralized storage.

- Risk: memory exports become inconsistent with DB path during partial rollout.
  Mitigation: move all artifact path derivation behind one `StoragePaths` abstraction before changing call sites.

- Risk: future demand for a single shared DB could be conflated with this feature.
  Mitigation: document the alternative clearly as a separate follow-on design with schema work.

- Dependency: tests currently encode the local-path assumption, especially around missing DB behavior and stdio setup, so they must be expanded rather than merely patched.

## Confidence Check

Strong sections:

- current architecture boundaries
- reason the per-project DB model fits the existing storage layer
- required code touch points

Weaker sections:

- exact env var naming and whether `KITTY_DB_PATH` should also exist
- whether plugins should opt in by default
- legacy migration expectations for non-local centralized layouts

The plan remains high confidence because those are product-surface decisions, not core architectural blockers. The implementation can proceed with `KITTY_STORAGE_ROOT` as the sole new primitive and leave explicit-DB-path support for a later refinement.

## Sources & References

- `src/cartograph/compat.py`
- `src/cartograph/server/main.py`
- `src/cartograph/__init__.py`
- `src/cartograph/web/main.py`
- `src/cartograph/server/tools/memory.py`
- `src/cartograph/storage/graph_store.py`
- `src/cartograph/storage/migrations/0001_baseline.sql`
- `src/cartograph/storage/migrations/0002_graph_reactive.sql`
- `tests/test_server.py`
- `tests/test_web.py`
- `tests/test_stdio_e2e.py`
- `plugins/kitty/.mcp.json`
- `plugins/kitty/.claude-plugin/plugin.json`
- `plugins/kitty/gemini-extension.json`
- `docs/plans/2026-03-28-005-feat-cat-rebrand-plan.md`
