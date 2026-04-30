# Plan-State Conventions

Plans under `docs/plans/` track their state in two layers:

- **Plan-level `status`** in YAML frontmatter — a single rollup field.
- **Per-unit `**State:**`** lines under each `### Unit N` (or `## UN`) header in the body —
  the authoritative source of truth.

The `units:` list in frontmatter is a denormalised cache the parser keeps in sync. The audit
hook (`uv run python scripts/plan_status.py audit`) fails pre-commit if the cache disagrees
with the body or if required-companion fields are missing.

## Status Taxonomy

Plan-level `status:` (frontmatter):

| Status | Meaning | Required companions |
|---|---|---|
| `draft` | Written but not yet approved for work | — |
| `active` | Approved; no units started | — |
| `in_progress` | At least one unit `in_progress` or `complete`, but not all `complete` | — |
| `complete` | Every unit `complete` (or `skipped`) | `implemented_in:` (commit hash, tag, or PR ref) |
| `superseded` | Replaced by another plan | `superseded_by:` (path to replacement plan) |
| `abandoned` | Explicitly dropped | `abandoned_reason:` (one-line text) |

Per-unit `state:`: one of `pending`, `in_progress`, `complete`, `skipped`. `skipped` requires a
`skipped_reason`.

## Unit Lifecycle

```
pending → in_progress    (set immediately before starting the unit)
in_progress → complete   (set after verification passes)
in_progress → pending    (set if the unit has to be aborted and retried)
* → skipped              (manual override with reason)
```

The plan-level `status` is auto-recomputed from the unit states by `set_unit_state`. The
explicit endpoints (`complete`, `superseded`, `abandoned`) override the rollup.

## Frontmatter shape

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
    title: <unit title>
    state: pending
---
```

## Body shape

Each unit gets a `**State:**` line immediately under its header. Two header styles are
supported:

```markdown
### Unit 1 — Filesystem watcher

**State:** complete — implemented in abc1234

- [x] Goal: ...
```

```markdown
## U1 — Source-of-truth, generators, and validator

**State:** in_progress

- [ ] Goal: ...
```

Headers inside fenced code blocks are masked by the parser, so schema illustrations cannot
contaminate parsed unit data.

## CLI

`scripts/plan_status.py` (also available via the `/kitty-plans` slash command):

```bash
# Dashboard report (default subcommand).
uv run python scripts/plan_status.py report
uv run python scripts/plan_status.py report --format json

# Validate every plan; exits non-zero on errors. Used by pre-commit.
uv run python scripts/plan_status.py audit

# Mutate one unit.
uv run python scripts/plan_status.py set-unit <plan> <unit-id> <state> [--commit HASH] [--reason TEXT]

# Mutate plan-level status.
uv run python scripts/plan_status.py set-status <plan> <status> \
    [--implemented-in HASH | --superseded-by PATH | --abandoned-reason TEXT]
```

Mutation commands write the file in place; the parser keeps the frontmatter cache and the
body `**State:**` lines in sync.

## Skills submodule follow-up

The `kitty:work` and `kitty:plan` skills (in
[`Kakise/cartographing-kitties-skills`](https://github.com/Kakise/cartographing-kitties-skills),
mounted at `plugins/kitty/skills/`) are the natural callers for `plan_status.py set-unit`.
A future submodule PR should:

1. Update `kitty:work`'s "Implementation loop" so each unit transitions to `in_progress`
   before the worker starts and to `complete` only after the validation gates pass.
2. Update `kitty:plan` so newly written plans use the new schema by default — frontmatter
   `units:` block plus `**State:** pending` lines under each unit header.
3. Reference this doc and `docs/plans/2026-04-29-001-feat-plan-status-tracking-plan.md` in
   the submodule PR description for context.

The framework agents under `plugins/kitty/agents/` do not need changes; they consume plan
context as text and do not own state transitions.

## Related

- `scripts/plan_state.py` — parser/serializer module (single source of truth).
- `scripts/plan_status.py` — CLI on top of `plan_state`.
- `tests/test_plan_state.py`, `tests/test_plan_status_cli.py` — schema and CLI tests.
- `docs/plans/2026-04-29-001-feat-plan-status-tracking-plan.md` — meta-plan that introduced
  the convention.
- `docs/plans/2026-04-29-002-feat-plugin-evolution-remaining-work-plan.md` — consolidated
  remaining-work tracker.
