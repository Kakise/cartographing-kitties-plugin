# Orchestration model — run boundaries, bundle handoff, dispatch paths

Canonical reference for how the `kitty` conductor orchestrates the workflow pipeline. This
replaces the former dual-runtime workflow contract: the framework now targets Claude Code
only, and the **main-loop orchestrator is the sole MCP client**.

## The conductor

For the pipeline (`brainstorm → plan → work → review`, or `lfg` end-to-end), `kitty` is a
conductor, not a passive router. Each turn it:

1. **Detects intent** and routes to the phase skill.
2. **Enforces the pipeline gates** (every phase skill also self-checks redundantly — see below).
3. **Owns the run journal** under `.pawprints/runs/<run-id>/`.
4. **Applies the AskUserQuestion gating contract** (`references/ask-user-protocol.md`).
5. **Builds the Context Bundle** and **dispatches** exactly one fan-out.

Agents are **MCP-free**: they read one curated bundle section and never call MCP or re-read
the codebase.

## Run boundaries

A *run boundary* is any MCP-gated step; it always returns to the main loop. The conductor —
never a dispatched script or agent — performs:

- graph context fetch (`get_file_structure`, `query_node`, `find_dependents`, …);
- the Context Bundle write;
- post-work re-index / `graph_diff` / `validate_graph`;
- `submit_annotations` (after each annotation batch — §8);
- plan-state mutation via the `plan_*` MCP tools;
- litter/treat memory writes.

Each dispatched fan-out is exactly **one** MCP-free batch. The conductor reconciles the
results, performs the MCP-gated post-steps, then advances to the next boundary. `kitty-work`
is therefore a **main-loop loop of per-unit runs**, not one uninterrupted pipeline.

## Context Bundle handoff

The conductor writes ONE curated bundle to `.pawprints/runs/<run-id>/bundle.md` (layout +
agent read-prologue + status envelope in `references/bundle-format.md`) and passes a SMALL
`args` object — bundle path, item ids, and resolved per-item `(model, effort)` tiers — to the
dispatched script. Large/formatted context lives in the bundle, never in `args` (arg-transport
limits). Agents return the unified envelope in `references/agent-output-contract.md` with a
mandatory `status` of `ok` / `bundle_unreadable` / `needs_more_context`.

## Complexity tiering

The orchestrator (not the script) computes each item's complexity class from graph signals and
resolves it to a `(model, effort)` tier per `references/dispatch-policy.md`
(`trivial → haiku·low`, `standard → sonnet·medium`, `hard → opus·high`, hardest verify
`opus·xhigh`). Scripts only **apply** `args.tiers`; they never classify.

## Dispatch paths (asymmetric)

`args.dispatch` defaults to `auto`: the conductor runs one cheap Workflow probe before
dispatching work items; a tool-unavailable / version-gate / flag-off / org-disabled error
commits the run to the **Task fallback**, other errors surface. The path is fixed once per run
and recorded in the journal.

- **Workflow path** — `agent({model, effort})` routes for real (verified in the Unit 0 gate).
- **Task fallback** — model tiering is advisory-only (a known platform limitation); `effort`
  travels as a prompt hint and the orchestrator validates each return against the same schema.

## Partial-failure reconciliation

Every dispatched item carries a ledger entry `{ id, status ∈ {pending, done, failed,
needs_context}, attempts }`. A throwing / empty / schema-invalid return counts as `failed`,
is re-dispatched once (bounded by `max_attempts = 2`), and is never silently dropped; an item
that exhausts its retries raises a blocking gate rather than being omitted.

## Redundant entry gates

Claude Code skills fire by description match, and slash-command invocation
(`/kitty:kitty-work <plan>`) bypasses the conductor entirely. So each pipeline phase skill
**self-checks its entry preconditions at the top of its body** independent of whether `kitty`
ran (`kitty-work`: an approved plan via `plan_status`; `kitty-review`: a reviewable diff;
`kitty-plan`: brainstorm output for net-new features; `kitty-brainstorm`: a topic to explore).
`scripts/validate_skills.py` asserts the `<!-- entry-self-check -->` sentinel is present in
each gated skill.

## Cross-session resume

`.pawprints/runs/` is git-ignored and disposable, so **git-tracked plan-state is the sole
durable resume authority**. Run-id `= <plan-slug>-<UTC-yyyymmddThhmmssZ>-<6char>` (plan-less
phases use a `phase-` prefix); `args.json` and the journal header record the absolute
`plan_path`. On a fresh-context resume the orchestrator rebuilds from plan-state and
re-dispatches any unit not `complete`-with-commit — recorded workflow run IDs are dead.

## See also

- `plugins/kitty/skills/kitty/references/bundle-format.md` — bundle layout + status envelope.
- `plugins/kitty/skills/kitty/references/dispatch-policy.md` — the complexity-tiering rubric.
- `plugins/kitty/skills/kitty/references/agent-output-contract.md` — the unified agent return.
- `docs/architecture/repo-boundaries.md` — what ships in the wheel vs. repo-local tooling.
