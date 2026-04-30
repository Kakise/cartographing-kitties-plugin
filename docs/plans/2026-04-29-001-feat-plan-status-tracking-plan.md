---
title: Plan Status Tracking & Roadmap Consolidation
type: feat
status: complete
date: 2026-04-29
origin: direct-request
implemented_in: 7afbfb8
units:
  - id: 1
    title: Plan-state schema and parser module
    state: complete
    implemented_in: 80129ba
  - id: 2
    title: kitty-plans status CLI
    state: complete
    implemented_in: a41a3cc
  - id: 3
    title: Slash command wiring (Claude + Codex)
    state: complete
  - id: 4
    title: Pre-commit and CI enforcement
    state: complete
  - id: 5
    title: Migration sweep across all 22 existing plans
    state: complete
    implemented_in: cdccd5c
  - id: 6
    title: Consolidated remaining-work plan (replaces R1–R9 roadmap)
    state: complete
    implemented_in: 96988bf
  - id: 7
    title: Convention documentation and skill follow-up note
    state: complete
    implemented_in: 7afbfb8
---

# Plan Status Tracking & Roadmap Consolidation — Implementation Plan

## Overview

Make plan and unit state durable, machine-readable, and enforceable, then use that infrastructure
to clean up the existing 22 plans and consolidate the remaining work into one umbrella plan.

The work is delivered as four interlocking deliverables that match the four parts of the request:

- **A.** A `kitty-plans` slash command (and underlying script) that reports the live status of every
  plan in `docs/plans/`, cross-referencing frontmatter, body unit-state, git history, and code
  signals.
- **B.** A richer plan-state schema — an extended frontmatter taxonomy plus per-unit `**State:**`
  lines — that survives interruptions of `kitty:work` so future runs can resume cleanly.
- **C.** A migration sweep that brings every existing plan onto the new schema with the correct
  rollup, including marking abandoned/superseded plans, ticking demonstrably-completed units, and
  recording `implemented_in:` commit hashes where derivable from `git log`.
- **D.** A consolidated "remaining work" plan that aggregates every still-pending unit across the
  unimplemented and partially-implemented sub-plans, replacing the current `R1–R9` roadmap.

## Problem Frame

The existing plans system has three concrete failures:

1. **Status is dead.** All 22 plans in `docs/plans/` carry `status: active` regardless of whether
   they're done, in-flight, abandoned, or superseded. There is no convention for distinguishing
   "shipped but checkboxes never ticked" from "actually unfinished" — a verification that took a
   manual pass over git history and the code tree to do today.
2. **Per-unit progress is ambient.** Units track progress only via free-form `- [ ]` checkboxes in
   the body. If `kitty:work` is interrupted mid-unit (process killed, agent crash, user `/exit`,
   PR rejected), the next run has no machine-readable signal of where to resume. Worse, the
   checkbox-tick discipline has not been followed: most shipped plans have zero checked boxes.
3. **The roadmap is stale.** `2026-04-23-001-feat-plugin-evolution-roadmap.md` is the parent of
   nine sub-plans; it describes ordering and gates that no longer reflect reality (R6 centrality
   is shipped but its sub-plan reads as 8% done; R9 annotation-quality is the active branch but
   isn't visible from the roadmap).

The fix is a single coherent change: define the schema, build the tool that reads/writes it,
enforce it via pre-commit, and run the one-time migration that brings the existing plans into
compliance. The consolidated remaining-work plan (D) is then a natural by-product of having an
audit tool that can list every pending unit across all plans.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R1. Define a plan-state taxonomy (frontmatter status + per-unit state) | Unit 1 |
| R2. Provide a parser/serializer module with backward-compatible defaults | Unit 1 |
| R3. Provide a CLI that reports plan status across the directory | Unit 2 |
| R4. Cross-reference plan status with git/code signals | Unit 2 |
| R5. Wire a `/kitty-plans` slash command (Claude + Codex variants) | Unit 3 |
| R6. Enforce the schema via pre-commit and CI | Unit 4 |
| R7. Migrate all 22 existing plans onto the new schema | Unit 5 |
| R8. Replace the R1–R9 roadmap with a consolidated remaining-work plan | Unit 6 |
| R9. Document the convention and capture follow-up for skill integration | Unit 7 |

## Scope Boundaries

**In scope:**
- New `scripts/plan_state.py` module (parsing, serialization, validation).
- New `scripts/plan_status.py` CLI built on top of `plan_state.py`.
- New `plugins/kitty/commands/kitty-plans.{toml,md}` slash-command pair.
- Pre-commit hook + CI hook that calls `plan_status.py audit --strict`.
- One-time migration sweep producing a single commit (or one commit per logical group) that
  rewrites every plan's frontmatter and adds `**State:**` lines under each unit header.
- New `docs/plans/2026-04-29-002-feat-plugin-evolution-remaining-work-plan.md` consolidating every
  still-pending unit, plus a `superseded_by:` pointer on the existing roadmap.
- New `docs/architecture/plan-state-conventions.md` describing the schema for human readers.
- Tests in `tests/test_plan_state.py` and `tests/test_plan_status_cli.py`.

**Out of scope:**
- Modifying `plugins/kitty/skills/`. That directory is a Git submodule pointing at
  `Kakise/cartographing-kitties-skills`; per `CLAUDE.md`, skill edits land via PRs against the
  submodule repo, not direct edits here. Unit 7 records the follow-up so a future submodule PR
  can teach `kitty:work` and `kitty:plan` to call `plan_status.py set-unit` mid-execution.
- Changing any existing slash command, MCP tool, or core graph code.
- Re-classifying any plan whose status is genuinely ambiguous beyond the categories already
  resolved manually in the conversation that produced this plan.
- Adding plan-level tagging beyond the `verifies:` field used by Unit 2's code-signal lookup.

## Context & Research

### Existing precedent the plan must follow

- `scripts/generate_agents.py`, `scripts/generate_manifests.py`, `scripts/validate_skills.py`,
  `scripts/generate_tool_reference.py` all share a `render_outputs / write_outputs / check_outputs
  / main` pattern with a `--check` mode used by pre-commit. The new `plan_status.py` mirrors that
  shape so the CI integration is mechanical.
- `plugins/kitty/commands/kitty-status.{toml,md}` is the precedent for paired Claude+Codex slash
  commands. The new `kitty-plans` pair must replicate the dual-format layout exactly.
- `.pre-commit-config.yaml` registers local `kitty-*` hooks via `entry: uv run python
  scripts/<name>.py [--check]`. Unit 4 adds one entry of the same shape.
- `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md` declares its child plans through a
  `plans:` list in frontmatter. The consolidated remaining-work plan keeps the same convention,
  with an additional `aggregates:` list pointing back at the source plans whose pending units it
  surfaces, and a `supersedes:` pointer that mirrors the inverse `superseded_by:` placed on the
  old roadmap.

### Annotation status

- Total nodes: 1152
- Annotated: 0 (0%) — the graph was just freshly indexed; semantic `search` is unreliable for this
  task, so the plan relies on file-structure data and direct file inspection rather than
  summary-driven retrieval.

### Plan inventory at planning time (2026-04-29)

The complete inventory and current rough classification (per the conversation that produced this
plan) — Unit 5 must reproduce this exactly:

| Plan file | New status |
|---|---|
| `2026-03-28-001-feat-ast-centric-agents-plan.md` | `complete` (commit `c2199ea`) |
| `2026-03-28-002-feat-web-explorer-plan.md` | `complete` (commits `5ad1145`, `8ed347d`) |
| `2026-03-28-003-feat-graph-view-plan.md` | `complete` (commits `b691992`, `8ed347d`) |
| `2026-03-28-004-feat-nested-box-treemap-plan.md` | `complete` (commit `8e95726`) |
| `2026-03-28-005-feat-cat-rebrand-plan.md` | `complete` (commits `231a403`, `b6e324e`) |
| `2026-03-28-006-feat-graph-reactive-engineering-plan.md` | `complete` (PR #3, merge `4469920`) |
| `2026-04-04-001-refactor-gemini-optimization-plan.md` | `superseded` (by Codex direction in `2026-04-21-002`) |
| `2026-04-21-001-feat-centralized-multi-project-storage-plan.md` | `complete` (`KITTY_STORAGE_ROOT` in `compat.py`) |
| `2026-04-21-002-refactor-codex-plugin-alignment-plan.md` | `complete` (5/5 checked) |
| `2026-04-23-001-feat-plugin-evolution-roadmap.md` | `superseded` (by `2026-04-29-002-...`) |
| `2026-04-23-002-feat-hybrid-search-plan.md` | `active` (no code signals yet) |
| `2026-04-23-003-feat-lsp-bridge-plan.md` | `active` |
| `2026-04-23-004-feat-language-expansion-plan.md` | `active` |
| `2026-04-23-005-feat-commit-history-plan.md` | `active` |
| `2026-04-23-006-feat-test-coverage-edges-plan.md` | `active` |
| `2026-04-23-007-feat-centrality-surface-plan.md` | `in_progress` (centrality field shipped) |
| `2026-04-23-008-feat-watch-mode-plan.md` | `active` |
| `2026-04-23-009-feat-shared-graph-cache-plan.md` | `active` |
| `2026-04-23-010-feat-annotation-quality-plan.md` | `in_progress` (current branch `annotation-quality-r9`) |
| `2026-04-27-001-feat-skills-submodule-repository-plan.md` | `complete` (commits `d7ec32f`, `b9c35c9`) |
| `2026-04-27-002-fix-memory-workflow-enforcement-plan.md` | `complete` (`memory-workflow.md` reference + skills) |
| `2026-04-27-003-feat-harness-context-engineering-plan.md` | `in_progress` (partial: `b23ea69`, `c5d3e17`) |
| `2026-04-29-001-feat-plan-status-tracking-plan.md` (this plan) | `active` |

## Key Technical Decisions

### Status taxonomy

Plan-level `status:` (in frontmatter):

| Status | Meaning | Required companions |
|---|---|---|
| `draft` | Written but not yet approved for work | — |
| `active` | Approved; no units started | — |
| `in_progress` | At least one unit `in_progress` or `complete`, but not all `complete` | — |
| `complete` | Every unit `complete` (or `skipped` with reason) | `implemented_in:` (commit hash, tag, or PR ref) |
| `superseded` | Replaced by another plan | `superseded_by:` (path to replacement plan) |
| `abandoned` | Explicitly dropped | `abandoned_reason:` (one-line text) |

Per-unit `state:` (one of `pending`, `in_progress`, `complete`, `skipped`).

### Schema layout: frontmatter rollup + body authority

**Frontmatter** holds the plan-level rollup and a unit-id table:

```yaml
---
title: ...
type: feat|fix|refactor
status: active|in_progress|complete|superseded|abandoned|draft
date: YYYY-MM-DD
origin: docs/brainstorms/...        # optional
parent: docs/plans/...              # optional
implemented_in: <commit-hash-or-pr> # required iff status == complete
superseded_by: docs/plans/...       # required iff status == superseded
abandoned_reason: "..."             # required iff status == abandoned
verifies:                           # optional — files/symbols whose existence proves implementation
  - src/cartograph/server/tools/lsp.py
units:
  - id: 1
    title: Filesystem watcher
    state: pending
  - id: 2
    title: Debounce + coalesce
    state: pending
---
```

**Body** holds authoritative per-unit detail. Each `### Unit N — <title>` (or `### Unit N: <title>`)
header gets a `**State:**` line directly under it:

```markdown
### Unit 1 — Filesystem watcher

**State:** complete — implemented in abc1234

- [x] Goal: ...
- [x] Files: ...
```

The body's `**State:**` line is the canonical source of truth. The frontmatter `units:` list is a
denormalized cache that the parser keeps in sync (validating in `--check` mode and fixing in
`set-unit` writes). The plan-level `status:` is itself a rollup computed from the unit states:

- All units `complete` (or `complete`+`skipped`) → `complete`
- Any unit `in_progress` or any mix of `complete`+`pending` → `in_progress`
- All units `pending` → `active` (or `draft` if explicitly so)
- `superseded` / `abandoned` are explicit and override the rollup.

`audit` (Unit 2) flags any plan whose body and frontmatter disagree.

### Unit-state lifecycle

`kitty:work` (in a future submodule PR — see Unit 7) drives state transitions:

```
pending → in_progress   (set immediately before starting the unit)
in_progress → complete  (set after verification passes)
in_progress → pending   (set if the unit has to be aborted and retried)
* → skipped             (manual override with reason)
```

Backwards-compat: a plan missing the new fields parses as if every unit is `pending` and the plan
is `active`. The migration sweep in Unit 5 is the only thing that ever has to interpret the legacy
checkbox-only format.

### Cross-reference signals (for `report` and `audit`)

The `kitty-plans report` command annotates each plan with three signals beyond what the file
declares:

- **Git signal:** `git log --grep=<plan-slug>` plus `git log --all -- <plan-path>` to surface the
  commits that mention the plan slug or modify the plan file. Used to suggest `implemented_in:`
  values when migrating.
- **Code signal:** if the plan's frontmatter declares a `verifies:` list (file paths or qualified
  names), each entry is checked for existence. This is opt-in and only used for `complete`-class
  plans where the writer wants the audit to assert a permanent invariant.
- **Branch signal:** if the current git branch name contains the plan's slug fragment (e.g.,
  branch `annotation-quality-r9` matches plan `2026-04-23-010-feat-annotation-quality-plan.md`),
  the report flags it as the likely active work.

## Open Questions

All questions material to architecture were resolved at planning time:

- **Slash command name:** `kitty-plans` (plural, mirrors `kitty-status`).
- **Where the parser lives:** `scripts/plan_state.py`, separate from the `plan_status.py` CLI for
  testability.
- **Authoritative source of truth:** body `**State:**` line; frontmatter is denormalized cache.
- **Submodule constraint:** skill files in `plugins/kitty/skills/` are not edited by this plan;
  Unit 7 documents what a follow-up submodule PR should do.
- **Migration approach:** one PR with one commit per logical group (legacy-complete sweep,
  superseded sweep, in-progress sweep, consolidated-remaining-work plan), so a reviewer can step
  through the changes.

Deferred (decide later, do not block this plan):

- Whether `kitty:work` and `kitty:plan` should call `plan_status.py set-unit` automatically. That
  edit must happen in the skills submodule.
- Whether `kitty-plans` should take a filter argument (e.g., `kitty-plans --status active`). The
  v1 command is filter-free; filtering can be a non-breaking addition.

## Implementation Units

### Unit 1 — Plan-state schema and parser module

**State:** complete — implemented in 80129ba

- [ ] Goal: A pure-Python module that parses the new plan format, serializes it back, computes
  rollups, and validates required fields, with no CLI surface and no I/O outside file reads.
- [ ] Files to create:
  - `scripts/plan_state.py`
  - `tests/test_plan_state.py`
  - `tests/fixtures/plans/legacy_minimal.md` (legacy frontmatter, no units list, free-form
    checkboxes)
  - `tests/fixtures/plans/new_format.md` (full new format, 3 units in mixed states)
  - `tests/fixtures/plans/superseded.md` (frontmatter with `superseded_by:`)
- [ ] Approach:
  - Dataclasses: `PlanFrontmatter`, `Unit`, `Plan` (= frontmatter + units + raw body).
  - Enums (or `Literal`): `PlanStatus`, `UnitState`.
  - `parse_plan(path: Path) -> Plan` reads YAML frontmatter (reuse `_parse_frontmatter` from
    `scripts/generate_agents.py` if importable; otherwise duplicate the small helper).
  - `parse_plan` also walks `### Unit N` headers in the body and reads the immediately-following
    `**State:** ...` line. If no `**State:**` line exists (legacy plan), unit state defaults to
    `pending`.
  - `serialize_plan(plan: Plan) -> str` round-trips: frontmatter rewrite + body rewrite that
    inserts/updates `**State:**` lines under each unit header without disturbing the rest of the
    body.
  - `compute_rollup(units: list[Unit]) -> PlanStatus` implements the rollup table from "Schema
    layout" above.
  - `validate(plan: Plan) -> list[ValidationError]` enforces required-companion fields per status
    (e.g., `complete` requires `implemented_in`).
  - Units in frontmatter and units in body must match by `id`; mismatch is a validation error.
- [ ] Patterns to follow:
  - Match `scripts/generate_agents.py` for YAML loading/dumping (uses `yaml.safe_load` /
    custom presenter).
  - Use absolute imports (`from scripts.plan_state import ...`) so tests can import cleanly; mark
    `scripts/__init__.py` if it does not exist (verify in implementation).
- [ ] Test scenarios:
  - **Happy path:** parse new-format fixture → expected `Plan` object; serialize back → byte-equal
    to input.
  - **Legacy compat:** parse legacy fixture → all units `pending`, plan status `active`.
  - **Rollup:** units `[complete, complete, pending]` → plan rollup `in_progress`; units all
    `complete` → `complete`; units `[complete, skipped, complete]` → `complete`.
  - **Validation errors:** plan `status: complete` without `implemented_in` → error; plan
    `status: superseded` without `superseded_by` → error; frontmatter unit list disagrees with
    body unit list → error.
  - **Round-trip with mutation:** parse → flip Unit 2 to `complete` with commit hash → serialize
    → re-parse → unit state and frontmatter unit cache both reflect the change.
- [ ] Verification:
  - `uv run pytest tests/test_plan_state.py` passes.
  - `uv run ruff check scripts/plan_state.py tests/test_plan_state.py` passes.
  - `uv run basedpyright --level error scripts/plan_state.py` passes.

### Unit 2 — `kitty-plans` status CLI

**State:** complete — implemented in a41a3cc

- [ ] Goal: A CLI script that reports plan status across `docs/plans/`, audits the schema, and
  mutates plan files in a controlled way (used by `kitty:work` follow-up integration).
- [ ] Files to create:
  - `scripts/plan_status.py`
  - `tests/test_plan_status_cli.py`
- [ ] Approach:
  - Argparse with subcommands: `report` (default), `audit`, `set-unit`, `set-status`.
  - `report`: scan `docs/plans/*.md`, parse each, render a table to stdout. Columns: file,
    title, type, status, units (e.g., `3/7 complete, 2 in_progress, 2 pending`), implemented_in,
    git-signal hint, branch-signal hint. Supports `--format json` for machine consumption.
  - `audit`: validate every plan; exit non-zero on any error. `--strict` treats body/frontmatter
    rollup disagreement as fatal.
  - `set-unit <plan> <unit-id> <state> [--commit HASH]`: mutate one unit's body `**State:**`
    line and the frontmatter cache atomically; recompute and write the plan-level rollup.
  - `set-status <plan> <status> [--implemented-in HASH | --superseded-by PATH | --abandoned-reason TEXT]`:
    set the explicit plan-level status, validating required companions.
  - Git signal: subprocess call `git log --oneline --all --grep=<slug>` + `git log --oneline --
    <plan-path>`. Cache results per process. Skip silently if `git` is unavailable.
  - `--check` flag on `audit` makes it pre-commit-friendly.
- [ ] Patterns to follow:
  - Argparse layout matching `scripts/validate_skills.py` (no Click dependency).
  - Subprocess git access matching the pattern in `src/cartograph/indexing/discovery.py` if
    importable; otherwise inline a small `subprocess.run` with `check=False` and explicit
    `text=True`.
- [ ] Test scenarios:
  - **Happy path:** point CLI at a temp `docs/plans/` containing two fixture plans → `report`
    output contains both titles, correct unit tallies; exit code 0.
  - **Audit success:** audit fixture plans that round-trip cleanly → exit 0.
  - **Audit failure:** audit a plan with `status: complete` and no `implemented_in:` → exit 1,
    error names the missing field.
  - **Mutation:** `set-unit fixture.md 2 complete --commit deadbeef` → re-parse shows unit 2
    state `complete`, body has `**State:** complete — implemented in deadbeef`, frontmatter cache
    matches, plan rollup recomputed.
  - **JSON format:** `report --format json` → valid JSON, schema-stable for downstream tools.
  - **Resume safety:** running `set-unit ... in_progress` twice in a row is a no-op on the
    second call (idempotent).
- [ ] Verification:
  - `uv run pytest tests/test_plan_status_cli.py` passes.
  - `uv run python scripts/plan_status.py audit` passes against the migrated `docs/plans/`
    (verified at the end of Unit 5).

### Unit 3 — Slash command wiring (Claude + Codex)

**State:** complete

- [ ] Goal: Expose the report via `/kitty-plans` in both Claude Code and Codex without duplicating
  command logic.
- [ ] Files to create:
  - `plugins/kitty/commands/kitty-plans.toml`
  - `plugins/kitty/commands/kitty-plans.md`
- [ ] Approach:
  - Mirror `kitty-status.toml` shape: a `description` and a `prompt` heredoc instructing the
    agent to invoke `uv run python scripts/plan_status.py report` and present the output. Pass
    `{{args}}` through so users can filter, e.g., `/kitty-plans --status active`.
  - Mirror `kitty-status.md` shape: YAML frontmatter with `description`, `allowed-tools` (just
    `Bash`), and a body of the same instructions.
  - Both files must agree on the underlying command and arg passthrough — the audit in Unit 4
    asserts this.
- [ ] Patterns to follow:
  - Exact frontmatter and TOML shape of `plugins/kitty/commands/kitty-status.{toml,md}`.
  - The `_source/manifests/plugin.yaml` generator regenerates manifests; ensure both new files
    are picked up by `scripts/generate_manifests.py --check` after the run.
- [ ] Test scenarios:
  - **Happy path:** `uv run python scripts/generate_manifests.py --check` exits 0 with the new
    command discovered.
  - **Skill validation:** `uv run python scripts/validate_skills.py` exits 0 (the kitty-plans
    files do not break skill discovery).
  - **Smoke:** Running the underlying bash command (`uv run python scripts/plan_status.py
    report`) against a temp plans directory produces non-empty output. (Optional — only added if
    the existing test harness has a similar smoke test for kitty-status.)
- [ ] Verification:
  - Both new files present and identical-in-intent.
  - `uv run python scripts/generate_manifests.py --check` passes.
  - `uv run pytest` passes any plugin-discovery tests.

### Unit 4 — Pre-commit and CI enforcement

**State:** complete

- [ ] Goal: Make schema drift impossible by failing pre-commit (and therefore CI) on any plan
  that is malformed, missing required companions, or whose body/frontmatter disagree.
- [ ] Files to modify:
  - `.pre-commit-config.yaml`
- [ ] Approach:
  - Add a `kitty-plan-status` local hook with `entry: uv run python scripts/plan_status.py audit
    --strict`, `language: system`, `pass_filenames: false`, glob-restricted to `^docs/plans/.*\.md$`.
  - Verify the hook fires under `uv run pre-commit run --all-files` and under per-file edits.
- [ ] Patterns to follow:
  - Same hook shape as `kitty-validate-skills` and `kitty-generate-tool-reference` already in the
    config.
- [ ] Test scenarios:
  - **Happy path:** after Unit 5's migration, `uv run pre-commit run kitty-plan-status
    --all-files` passes.
  - **Failure path:** introduce a deliberate inconsistency (set a unit body state to
    `complete` without updating the frontmatter cache) → hook fails with a clear message
    pointing at the file and unit id; revert, hook passes.
- [ ] Verification:
  - The pre-commit hook fires automatically when a plan file is modified.
  - CI on a follow-up PR that breaks a plan fails on this hook before any other.

### Unit 5 — Migration sweep across all 22 existing plans

**State:** complete — implemented in cdccd5c

- [ ] Goal: Bring every existing plan onto the new schema with the correct status, with
  demonstrably-completed units flipped to `complete`, abandoned/superseded plans marked, and
  partial plans recording per-unit state that matches the code reality.
- [ ] Files to modify (all under `docs/plans/`):
  - All 22 existing plan files listed in the inventory in "Context & Research".
- [ ] Approach:
  - Use `plan_status.py set-status` and `plan_status.py set-unit` (already shipped in Unit 2)
    rather than hand-editing — the migration is itself the first non-trivial dogfood of the CLI.
  - Group commits logically:
    1. **Bulk-complete sweep** — flip every plan in the `complete` row of the inventory table to
       `status: complete` with the recorded `implemented_in:` commit hash. Body unit states are
       all set to `complete` since the work shipped.
    2. **Superseded sweep** — flip `2026-04-04-001-refactor-gemini-optimization-plan.md` to
       `superseded` (with `superseded_by: docs/plans/2026-04-21-002-refactor-codex-plugin-alignment-plan.md`).
       The R1–R9 roadmap is set to `superseded` only after Unit 6 lands the replacement plan.
    3. **In-progress sweep** — for `2026-04-23-007-feat-centrality-surface-plan.md`,
       `2026-04-23-010-feat-annotation-quality-plan.md`, and
       `2026-04-27-003-feat-harness-context-engineering-plan.md`, flip the plan to `in_progress`
       and tick the units that are demonstrably done. Each such transition is justified inline
       in the commit message with a commit-hash pointer (e.g., centrality-surface unit "core
       centrality field" → `complete` (per CLAUDE.md `centrality` field, ranked surface in
       `query.py`); annotation-quality unit ↔ commits on the active branch
       `annotation-quality-r9`).
    4. **Active sweep** — for the seven remaining `active` plans (hybrid-search, lsp-bridge,
       language-expansion, commit-history, test-coverage-edges, watch-mode, shared-graph-cache),
       only the schema is upgraded: frontmatter `units:` cache populated from the body's existing
       `### Unit N` headers, plan rollup recomputed (stays `active`), body unchanged except for
       new `**State:** pending` lines under each unit.
  - For each plan touched, ensure `verifies:` is populated only when the writer can name a
    permanent code artifact (the inventory above carries those for the obvious cases:
    `KITTY_STORAGE_ROOT` for centralized-storage, `centrality` field for centrality-surface,
    etc.).
- [ ] Patterns to follow:
  - One commit per logical group above so a reviewer can step through.
  - Use the CLI from Unit 2; do not hand-edit a plan unless `plan_status.py` cannot express the
    required change (in which case extend the CLI before continuing).
- [ ] Test scenarios:
  - **Happy path:** after the sweep, `uv run python scripts/plan_status.py audit --strict`
    exits 0 against the entire `docs/plans/` directory.
  - **Roundtrip:** `uv run python scripts/plan_status.py report --format json` lists 23 plans
    (the existing 22 plus this plan) with the expected status distribution.
  - **No accidental changes:** plans whose status remained `active` have unchanged bodies (only
    frontmatter additions and `**State:** pending` lines under unit headers). `git diff` reviewed
    file-by-file.
- [ ] Verification:
  - `uv run python scripts/plan_status.py audit --strict` exits 0.
  - `uv run pre-commit run --all-files` exits 0.
  - The full plan inventory in the report matches the table in "Context & Research".

### Unit 6 — Consolidated remaining-work plan

**State:** complete — implemented in 96988bf

- [ ] Goal: Replace the existing R1–R9 roadmap with a single plan that lists every still-pending
  unit across the active and partial sub-plans, so a future contributor can pick a unit and run
  `kitty:work` directly without having to compose context across nine files.
- [ ] Files to create / modify:
  - Create: `docs/plans/2026-04-29-002-feat-plugin-evolution-remaining-work-plan.md`
  - Modify: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md` (set
    `status: superseded` and `superseded_by:` pointing at the new plan; this happens *after* the
    new plan is committed so the link target exists).
- [ ] Approach:
  - The new plan is a tracking index, not a redesign. Each unit summarises one pending unit from
    a source plan and links back to that plan for design depth.
  - Frontmatter:
    ```yaml
    title: Plugin Evolution — Remaining Work
    type: feat
    status: active
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
    ```
  - Body sections: Overview, Problem Frame (very short — point at this plan and the originals),
    Sequencing (carry forward the Phase α–ε ordering from the old roadmap, updated for what's
    already done), Implementation Units (one per remaining unit, grouped by source plan).
  - Each remaining-work unit body:
    ```markdown
    ### Unit N — <source plan slug> :: Unit <K> (<short title>)

    **State:** pending
    **Source:** docs/plans/<source-plan>.md (Unit <K>)

    - [ ] Goal: <copied from source plan, one line>
    - [ ] Reference: see source plan for full design.
    ```
  - The unit count: enumerate every still-`pending` unit across the aggregated source plans
    (use `plan_status.py report --format json --status pending-units` or a direct query — extend
    Unit 2 with this filter if needed; extension is small enough to fit in this unit if a new
    flag is required).
- [ ] Patterns to follow:
  - Match the roadmap's section structure so a reader familiar with the old roadmap can navigate
    the new one.
  - Keep design detail in the source plans; do not duplicate it here.
- [ ] Test scenarios:
  - **Audit:** `plan_status.py audit --strict` passes including the new plan.
  - **Cross-link integrity:** every `aggregates:` entry resolves to an existing file; every
    source-plan unit referenced from the body exists in that source plan.
  - **Roadmap supersession:** `plan_status.py report` shows the old roadmap as `superseded` with
    the correct `superseded_by:` and the new plan as `active`.
- [ ] Verification:
  - `plan_status.py audit --strict` passes.
  - Manual scan of the new plan's unit list against the union of pending units in the aggregated
    plans matches.

### Unit 7 — Convention documentation and skill follow-up note

**State:** complete — implemented in 7afbfb8

- [ ] Goal: Document the new plan-state convention for human contributors and capture the
  follow-up that the skills submodule must take on.
- [ ] Files to create / modify:
  - Create: `docs/architecture/plan-state-conventions.md`
  - Modify: `CLAUDE.md` (one new bullet under "Generated harness artifacts" pointing to the
    convention doc; add a `Plan tracking` row to the architecture table or under Workflow
    Pipeline).
  - Modify: `README.md` only if it currently mentions plan tracking (verify in implementation;
    skip otherwise).
- [ ] Approach:
  - `plan-state-conventions.md` covers: status taxonomy table, per-unit state lifecycle, the
    body/frontmatter contract, the `verifies:` field, and how to use `kitty-plans` /
    `plan_status.py`. One page, no boilerplate.
  - Add a short "Skills submodule follow-up" section that explicitly captures: a future PR
    against `Kakise/cartographing-kitties-skills` should teach `kitty-work` and `kitty-plan` to
    call `plan_status.py set-unit ... in_progress` before starting a unit and `... complete`
    after verification, so resume-after-failure becomes automatic. Reference this plan and the
    plan-state-conventions doc so the submodule PR has clear context.
- [ ] Patterns to follow:
  - Keep `docs/architecture/` flat (existing files: `codex-workflow-contract.md`,
    `repo-boundaries.md`).
  - CLAUDE.md edit is one or two lines; follow the existing terse tone.
- [ ] Test scenarios:
  - **Linking:** `docs/architecture/plan-state-conventions.md` is referenced from CLAUDE.md and
    from the new consolidated plan's frontmatter (in a comment block, not a frontmatter field).
  - **No regressions:** `uv run pytest` and `uv run pre-commit run --all-files` both pass after
    these doc changes.
- [ ] Verification:
  - The convention doc renders cleanly and is reachable from CLAUDE.md.
  - The follow-up section unambiguously names the submodule repo, the skills involved
    (`kitty-work`, `kitty-plan`), and the CLI command they should call.

## System-Wide Impact

- **New scripts:** `scripts/plan_state.py`, `scripts/plan_status.py`. Mirrors the existing
  `scripts/generate_*.py` and `scripts/validate_skills.py` shape; no new external dependency.
- **New slash command:** `/kitty-plans` adds one entry to the plugin command surface. Total
  commands grows from 3 to 4.
- **New pre-commit hook:** one `kitty-plan-status` local hook. Adds <1s to pre-commit runs.
- **New tests:** `tests/test_plan_state.py`, `tests/test_plan_status_cli.py`, plus fixtures
  under `tests/fixtures/plans/`. Existing tests untouched.
- **Plan format change:** every plan in `docs/plans/` gains the new frontmatter fields and
  `**State:**` lines. Bodies are otherwise unchanged for `active` plans.
- **No code changes** in `src/cartograph/`. The MCP server, the parser, and the storage layer
  are untouched.
- **No breaking change** to any existing skill or command. The skills submodule is unchanged
  (Unit 7 only documents the follow-up).

## Risks & Dependencies

| Risk | Mitigation | Unit |
|---|---|---|
| Migration mis-classifies a plan | Inventory in this plan locks the classification; the migration is mechanical against that table; reviewer steps through one logical commit per group | 5 |
| Pre-commit hook becomes flaky on legacy plans before migration lands | Land the hook in the same PR as the migration sweep; if split, the hook stays disabled until Unit 5 ships | 4, 5 |
| `plan_status.py set-unit` writes corrupt YAML if the parser regex is fragile | Round-trip tests in Unit 1 cover serialize → parse → byte-equal; CLI calls go through the parser, not regex | 1 |
| Skills cannot mutate plans without modifying the submodule | Out-of-scope; Unit 7 captures the follow-up explicitly so it is not lost | 7 |
| `git log --grep` reports false positives that mislead `implemented_in:` suggestions | The CLI suggests, the migration writer commits the hash by hand only when confident; `audit` does not require `implemented_in:` to verify against git, only to be present | 2, 5 |
| Frontmatter `units:` cache and body `**State:**` lines drift in future hand-edits | `audit --strict` fails on disagreement; pre-commit catches it before merge | 4 |
| Consolidated remaining-work plan duplicates instead of links | Unit 6's review checks that each unit body links back to a source plan and copies the goal line only | 6 |

**External dependencies:** none beyond what `pyproject.toml` already declares.

**Internal dependencies:** Unit 2 depends on Unit 1; Unit 4 depends on Unit 2; Unit 5 depends on
Units 1–4 (uses the CLI and the audit hook); Unit 6 depends on Unit 5 (status is correct before
the consolidation enumerates pending units); Unit 7 depends on Units 1–6 (documents the final
shape).

## Sources & References

- Existing roadmap (will be superseded): `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`
- Architecture contract referenced by the schema: `docs/architecture/codex-workflow-contract.md`
- Submodule boundary referenced by Unit 7: `docs/architecture/repo-boundaries.md`
- Generator-script precedent: `scripts/generate_agents.py`, `scripts/validate_skills.py`,
  `scripts/generate_tool_reference.py`
- Slash-command precedent: `plugins/kitty/commands/kitty-status.{toml,md}`
- Pre-commit precedent: `.pre-commit-config.yaml` (entries `kitty-validate-skills`,
  `kitty-generate-*`)
- Plan inventory and classification: derived from the conversation that produced this plan
  (cross-referenced against `git log --oneline -100` and code signals in `src/cartograph/`)

## Handoff

This plan is ready for `kitty:work`. Recommended execution order is the unit number order
1 → 7. Units 1–4 land the infrastructure; Unit 5 dogfoods it on the existing 22 plans; Unit 6
produces the consolidated remaining-work plan as a by-product of having the audit tool; Unit 7
closes the loop with documentation and a captured follow-up for the skills submodule.

The plan itself is the first test of resume-after-failure: after each unit lands, the plan's
frontmatter rollup advances from `active` → `in_progress` → `complete`, with each unit's
`**State:**` line ticking forward through `pending` → `in_progress` → `complete`. If
`kitty:work` is interrupted between units, the next run reads the same file and resumes at the
first unit whose state is `pending` or `in_progress`.
