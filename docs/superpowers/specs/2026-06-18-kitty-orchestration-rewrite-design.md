---
title: Kitty Orchestration Rewrite — Workflow-First Dynamic Orchestration with Graph-as-Context
type: refactor
status: draft
date: 2026-06-18
revision: 2
revision_note: >
  v2 incorporates a 6-lens adversarial red-team (16 confirmed findings) plus the
  plan-state shipping fix. Major changes: the run-boundary model (§3), the fallback
  coordination contract (§5), partial-failure reconciliation (§6), plan-state as the
  sole cross-session authority shipped via cartograph.planning (§10), strict LOC
  discipline on harness-produced code only (§12, framework files keep the existing ≤500
  cap), and redundant phase self-check gates (§7).
origin: superpowers:brainstorming session 2026-06-18
verifies:
  - plugins/kitty/_source/skills/
  - plugins/kitty/_source/agents/
  - scripts/generate_agents.py
  - scripts/generate_skills.py
  - scripts/validate_skills.py
  - scripts/plan_state.py
  - scripts/plan_status.py
---

# Kitty Orchestration Rewrite

Rewrite the Cartographing Kittens skill/sub-agent layer so orchestration is
**dynamic, parallel, complexity-routed, and repeatable across sessions**, using the
graph as the primary context substrate and the Claude Code **Workflow tool** as the
orchestration engine where available — degrading to Task-tool dispatch where it is not.

This document is the validated design and the single source of truth for the
implementation plan. It has survived a 6-lens adversarial review; the §17 risk
register records what remains genuinely uncertain.

---

## 1. Motivation & findings

The framework today orchestrates entirely through **prose**: skill bodies tell Claude
to "spawn 4 research agents in parallel" or "spawn the impact reviewer when 3+ files
change." All 10 sub-agents hardcode `model: claude-sonnet-4-6`. There is **no**
complexity-based routing anywhere.

Four findings (Claude Code GitHub issues + docs, June 2026) reshape what is achievable.
**Two of the four carry load-bearing assumptions that were unverified at author time;
both have since been partially validated empirically (§13).**

| # | Finding | Source | Consequence |
|---|---------|--------|-------------|
| F1 | Per-subagent model selection via `model:` frontmatter / env / Task param is **broken** — everything resolves to the parent model. | [#43869](https://github.com/anthropics/claude-code/issues/43869), #67942, #67794, #68147 | "Smart dispatch" cannot ride agent definitions. The working path is the Workflow tool's `agent(prompt, {model, effort})`. **VERIFIED (Unit 0, §13):** a probe spawned haiku/sonnet/opus agents that each reported their distinct, tier-matching model id — the Workflow `agent()` resolver is exempt from #43869. (The Task/fallback path remains broken.) |
| F2 | A plugin **cannot ship or expose a workflow** — no `workflows/` slot; named-resolution is buggy; `scriptPath` drops `args`. | [#66032](https://github.com/anthropics/claude-code/issues/66032), [#63876](https://github.com/anthropics/claude-code/issues/63876) | Ship the script as a skill **`references/` file** and pass it **inline** via `Workflow({ script: <contents>, args })`. **VALIDATED (§13):** the inline `script:` param exists and works in this runtime; `args` as an object + JSON.parse prologue works. |
| F3 | The Workflow tool is **paid-plan + flag + version (≥2.1.154) gated**, user/org-disableable, with **no runtime availability API**. | docs/workflows, #65206 | The Task-tool **fallback is the common path**. Both paths must be first-class but they are **not symmetric** — see §5. Path selection needs an explicit mechanism (§5), since there is no API to query. |
| F4 | MCP tools are **unavailable inside subagents** (empty registry); nested subagents impossible; parallel Task dispatch can **silently duplicate** and storms on 429/529 with **no backoff**. | [#64909](https://github.com/anthropics/claude-code/issues/64909), #19077, #64080, #64177, #68502 | **Only the main-loop orchestrator calls MCP.** Agents are MCP-free. The Workflow runtime supplies concurrency caps + retries the raw Task path lacks → the fallback must hand-roll bounded coordination (§5). Topology is flat. |

**Honest limitation (must be in user-facing docs):** because of F1+F3, true model-tier
routing only takes effect when the user has the Workflow tool enabled. On the fallback
path we lose, specifically: **(a) runtime model-tier routing, (b) runtime effort
control, (c) pipeline wall-clock overlap, and (d) runtime concurrency/dedup/backoff
storm protection.** We retain smart **fan-out shaping**, smart **agent/lens selection**,
and **prompt-injected effort hints** (a best-effort proxy, not the runtime knob). We
lose orchestration *quality* on the fallback, never *capability*.

### 1.1 Secondary bug-workaround index

The F1–F4 table covers the structural findings; these are the remaining issues this
design works around, with their one-line mitigation:

| Bug | Mitigation |
|-----|------------|
| #68969 args arrive JSON-string-coerced | Required prologue `const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})`; validator-enforced (§11). |
| #63102 no byte-exact arg transport | Keep `args` **small + quote-light** — paths and IDs only; large/formatted context goes in `bundle.md`, never in args (§3.2 step 5). |
| #67906 / #50267 path/permission allowlists don't inherit into subagents | Orchestrator (main loop) owns all writes; agents are read-only (annotator's scoped `Bash` excepted). Agent `Read` of the session-local run-dir and the annotator's `Bash` are pre-authorized in the skill `allowed-tools`; in no-prompt pipeline mode a permission wall fails the item into the §6 ledger rather than hanging. |
| #57751 plan-mode prompt-cache bleed into subagents | Orchestration runs **outside** plan mode; the bundle is an explicit input, never inherited context. |
| #63725 Workflow over-triggers on the bare word "workflow" | Authoring guideline + validator audit of the precise unfenced trigger token (§11). |

---

## 2. Goals & non-goals

### Goals
1. **Graph-as-context, no context rot.** The orchestrator fetches structural context via the kitty MCP server and hands agents a single curated **Context Bundle**.
2. **Minimal agent file reading.** Agents read *one* bundle file (+ targeted source lines for verification), never the codebase at large. Agents never call MCP.
3. **Dynamic parallelism + complexity-routed dispatch** via the Workflow tool where available.
4. **Repeatable across sessions.** Orchestration scripts are versioned, shipped, CI-tested. Plan-state (git-tracked) lets a fresh context resume without re-doing completed work.
5. **`kitty` is a real orchestrator** that detects intent, enforces pipeline gates, owns the run journal, and dispatches — with gate enforcement made **redundant** in each phase skill (§7), because no harness guarantees the router fires first.
6. **Superpowers-grade discipline** in every skill: trigger-only descriptions, hard gates, rationalization tables, red-flag lists, two-gate review, verification-before-completion.
7. **Strict LOC discipline on harness-produced code** (§12). Framework files keep the existing ≤500-line body convention — no tighter cap.

### Non-goals
- Fixing the upstream Claude Code bugs (we design *around* them).
- Codex / dual-runtime support — **removed**.
- A custom subagent runtime — we use Workflow + Task only.
- Marketplace-distributable workflows (blocked by #66032).

---

## 3. Core architecture — Context Bundle handoff + run boundaries

### 3.1 The principle of run boundaries

A workflow script runs inside the Workflow runtime, **not** the main loop, so it is
**MCP-free** (F4). Therefore:

> **A workflow run performs exactly one MCP-free fan-out. Every MCP-gated step is a
> RUN BOUNDARY: it ends the run, returns control to the main-loop orchestrator (the
> sole MCP client), which performs the MCP work and — if more agent work follows —
> re-invokes the workflow (reusing `resumeFromRunId` so completed agents are not
> re-run).**

MCP-gated steps that force a run boundary: building/enriching the bundle, `needs_more_context`
expansion, kitty-work's post-write `index_codebase` + `graph_diff` + `validate_graph`,
annotation `submit_annotations`, and all plan-state mutations.

Consequence: **workflows shine for parallel fan-outs** (research lenses, review
dimensions, annotation batches). **Sequential, MCP-gated loops** (kitty-work's per-unit
implement→re-index→validate→commit) are **main-loop-driven loops of single-fan-out
workflow runs**, not one uninterrupted pipeline.

### 3.2 The data flow

```
MAIN-LOOP ORCHESTRATOR  (sole MCP client; owns all run boundaries)
  1. Read plan-state (authoritative resume) + run journal (best-effort working ctx)
  2. Fetch graph context via kitty MCP (get_file_structure, query_node,
     batch_query_nodes, find_dependents/_dependencies, rank_nodes,
     get_context_summary, query_litter_box, query_treat_box)  — graph first, no raw reads
  3. Write ONE curated Context Bundle → .pawprints/runs/<run-id>/bundle.md
     (includes a "Memory lessons" section from litter/treat box — §15)
  4. Compute per-item complexity score → (model, effort) tier
  5. Build SMALL args: { bundlePath(absolute), items[], tiers{}, lensRefs{}, dispatch }

  ── RUN BOUNDARY: dispatch one fan-out ──
  workflow path:  Workflow({ script:<ref contents>, args })   // §5.1
  fallback path:  bounded Task coordination loop                // §5.2

AGENTS  (workflow- or Task-spawned — same DATA contract, see §5 for path asymmetry)
  • Prologue: assert bundle file readable & non-empty; else return {status:'bundle_unreadable'}
  • Read ONE bundle section (curated graph digest); read targeted source lines only to verify
  • NO MCP, NO codebase exploration
  • Return schema-validated structured output, or {status:'needs_more_context', specifics}

  ── back in MAIN LOOP ──
  6. Reconcile results (§6): re-dispatch failed/needs_context items (bounded), gate on exhaustion
  7. MCP-gated post-steps as needed (re-index/validate, submit_annotations) — a RUN BOUNDARY
  8. Mutate plan-state via MCP plan tools (§10); append run journal
  9. Write memory; report; gate next phase
```

**Why this shape wins on every axis:** the bundle *is* the graph-as-context (goal 1)
and the only thing agents read (goal 2); agents are MCP-free → dodges F4; flat topology
→ dodges #19077; the run-boundary rule makes the MCP-free constraint *coherent* instead
of a hidden contradiction. The script cannot read files, but the agents it spawns can
`Read` the bundle — that single, guarded read is the allowed exception.

**Architectural principle (updates CLAUDE.md "Kittens-First"):** *Only the main-loop
orchestrator calls MCP. Agents receive graph intelligence; they never gather it.* The
graph still drives everything — the MCP calls relocate to the orchestrator.

---

## 4. Smart dispatch — complexity tiering

The **main-loop orchestrator** (not the script) computes a complexity class per item
from graph signals it already holds, and passes the resolved `(model, effort)` per item
in `args.tiers`. The script just applies them. (The rubric lives once in
`references/dispatch-policy.md`; scripts never hard-code it.)

**Signals:** `nodes_in_scope`, `max_centrality` (cached), `files_touched`, `blast_radius`,
`bundle_section_tokens`, `finding_severity` (verify stage).

| Class | Predicate | model · effort |
|-------|-----------|----------------|
| **trivial** | `nodes ≤ 1` ∧ `max_centrality < 0.1` ∧ `files == 1` ∧ no public API ∧ `section_tokens < 1000` | `haiku` · low |
| **hard** | `files ≥ 3` ∨ `blast_radius ≥ 15` ∨ `max_centrality ≥ 0.5` ∨ architectural/new-file ∨ verify of `P0`/`P1` | `opus` · high (`xhigh` for hardest verify) |
| **standard** | otherwise | `sonnet` · medium |

> **Tiering has real effect on the workflow path — VERIFIED in Unit 0 (§13): probe agents
> at haiku/sonnet/opus each reported distinct, tier-matching model ids.** On the fallback
> path tiers are **recorded for forward-compat only — no runtime effect today (F1/#43869
> on the Task path)**; effort is conveyed as a prompt hint (best-effort proxy).

---

## 5. Dispatch paths (asymmetric)

Both paths consume **the same bundle + prompts + JSON schemas (shared fixtures)**. They
are **not** "the same call with a different spawn primitive": the Workflow runtime
provides coordination guarantees the fallback must reimplement as bounded, prose-driven
logic. This asymmetry is explicit, not hidden.

### 5.1 Workflow path
`Workflow({ script:<ref contents>, args })`; `pipeline`/`parallel`; `agent(prompt,
{model, effort, agentType, schema})`. The runtime supplies concurrency caps, retries,
and schema enforcement. One run = one MCP-free fan-out (§3.1).

### 5.2 Fallback coordination contract
The fallback orchestrator is the main-loop model executing skill prose — no scheduler,
no semaphore, no real timer. It therefore commits to **bounded** coordination:

- **Concurrency:** dispatch SERIALLY or in fixed batches of `N` (default 1–2) with an
  explicit between-batch gate (collect + reconcile prior batch before issuing the next).
  Accept lower throughput as honest degradation. No unbounded fan-out is ever issued.
- **Dedup (against #64080 silent duplication):** a **journal-backed claimed-set** —
  append `item-id` to the run journal **before** each spawn; on resume, skip claimed
  items. A prose "dedup" instruction cannot see *silent* duplication, so the real
  mitigation is to never fan out unboundedly.
- **Backoff (against #64177/#68502):** a prose orchestrator cannot sleep; on 429/529 it
  re-dispatches **fewer** items next turn and surfaces the throttle to the user.
- **Schema enforcement (no `schema` param on Task):** the orchestrator validates each
  return against the same JSON schema; on failure it re-dispatches the same agent once
  with the validation error appended (mirrors the `needs_more_context` "max one
  follow-up" idiom); a second failure → journaled failure (§6), never silent acceptance.
- **`needs_more_context`** re-dispatches count against the same concurrency cap and the
  item's single-expansion budget.

### 5.3 Path selection (no availability API — F3)
- Default `args.dispatch = 'auto'`: the orchestrator attempts a single cheap Workflow
  probe **before any work items are dispatched**; a tool-unavailable / version-gate /
  flag-off / org-disabled error commits the run to the fallback. Other errors surface.
- Override: `args.dispatch ∈ {'workflow','task','auto'}` for known-good/known-bad setups.
- The chosen path is fixed **once per run** and recorded in the journal. If Workflow
  fails *after* items were dispatched, reconcile via the per-item ledger (§6) and
  re-dispatch only items with no recorded result — never double-process (#64080).

---

## 6. Partial-failure reconciliation & the item ledger

Storms (#68502) and 429/529 make partial batch failure the **expected** case. The run
journal therefore carries a **per-item ledger** for every fan-out (this is journal-level
working state, distinct from plan-state units, §10):

- Each dispatched item: `{ id, status ∈ {pending, done, failed, needs_context}, attempts }`.
- On batch completion the orchestrator re-dispatches **only** items whose status ≠ `done`,
  bounded by `max_attempts` (default 2). **Transport errors (429/timeout) AND
  schema-invalid/empty returns both count as `failed`.**
- Exhausted-retry items are marked `failed` and raised as a **BLOCKING gate** — the
  orchestrator does **not** proceed to synthesis/report with silently-missing items.
- The §11 harness asserts each `*.orch.js` records a thrown/empty/schema-invalid agent
  result as `failed` (re-dispatch or gate), never silently omits it.

`plan_state.py`'s `UnitState` stays `{pending, in_progress, complete, skipped}` — there
is no unit-level `failed`; fan-out failures live in the journal ledger, not plan-state.

---

## 7. The `kitty` orchestrator + redundant gates

`kitty` is rewritten from a routing *heuristic* into a *conductor*: intent detection →
route to the phase skill → enforce pipeline gates → own the run journal → apply the
AskUserQuestion gating contract → build the bundle and dispatch.

**Activation reality (C14):** Claude Code skills fire by **description match**, not an
always-on hook — even `using-superpowers` is description-triggered. Nothing guarantees
`kitty` loads before another skill, and slash-command invocation (`/kitty:kitty-work
<plan>`) bypasses it entirely. Therefore gate enforcement is **redundant, not
conductor-exclusive**:

- Every pipeline phase skill **self-checks its entry preconditions at the top of its
  body**, independent of whether `kitty` ran:
  - `kitty-work`: assert an approved plan exists (file present ∧ frontmatter status
    ready/approved, via the `plan_status` MCP tool); else refuse and route to `kitty-plan`.
  - `kitty-review`: assert a since-baseline diff or uncommitted changes exist; else explain.
  - `kitty-plan`: for net-new features, confirm brainstorm output exists.
- Each self-check **lazily creates/attaches the run journal** if the conductor did not.
- `disable-model-invocation: true` (already on work/annotate/lfg) blocks model-triggered
  bypass for those three but **not** slash-command bypass — so self-checks are required.
- `validate_skills.py` asserts each gated phase skill body contains its self-check (§11).

---

## 8. Agent roster (hybrid — 7 agents)

| Agent | Kind | Lens / role | Spawn | Tools |
|-------|------|-------------|-------|-------|
| `librarian-kitten` | **consolidated** | architecture \| pattern \| flow \| impact | conditional (research) | Read, Grep, Glob |
| `expert-kitten-correctness` | distinct | logic / edge / state | always-on | Read, Grep, Glob |
| `expert-kitten-testing` | distinct | coverage gaps | always-on | Read, Grep, Glob |
| `expert-kitten-impact` | distinct | blast radius | conditional (≥3 files / public API) | Read, Grep, Glob |
| `expert-kitten-structure` | distinct | architecture, naming, imports, **oversized-file flag** | conditional (new files / module change) | Read, Grep, Glob |
| `expert-kitten-context` | distinct | bundle redundancy / over-fetch | conditional (bundle >10k tokens) | Read, Grep, Glob |
| `cartographing-kitten` | distinct | batch annotation | conditional (≥50 pending) | Read, Grep, Glob, Bash |

**Changes from today:**
- 4 librarians → 1 `librarian-kitten`; the four lenses move to versioned
  `references/lenses/{architecture,pattern,flow,impact}.md`, injected at dispatch.
- **MCP removed from every agent allowlist** (F4). `needs_more_context` returns to the
  orchestrator (a run boundary, §3.1), which fetches and re-dispatches (max 1 expansion).
- **Annotator write-back is a run boundary:** `cartographing-kitten` produces annotation
  JSON into its return; the **main-loop orchestrator** calls `submit_annotations` after
  the batch (agents cannot — it is MCP-only). Stated explicitly because the current skill
  insists submission cannot be done "by script."
- `expert-kitten-structure` owns the produced-code oversized-file finding (§12, flag-only).
- Each agent body ≤ 200 lines; shared output envelope + bundle-consumption rules live in
  `references/agent-output-contract.md` + `references/bundle-format.md`, referenced.
- Agents keep `model:` frontmatter at a sensible default (forward-compat) but the
  framework never relies on it (F1).

Output contracts unchanged in shape (research-summary envelope; review findings JSON
with `severity`/`category`/`location`/`issue`/`guidance`/`confidence`/`autofix_class`),
plus the mandatory `status` field (`ok`/`bundle_unreadable`/`needs_more_context`).

---

## 9. Per-skill rewrite

Each orchestrating skill gets the §3 handoff shape, a shipped
`references/workflows/<skill>.orch.js`, superpowers hardening, an entry self-check (§7),
and a body within the existing ≤500-line convention (§12).

| Skill | Orchestration after rewrite |
|-------|------------------------------|
| `kitty` | Conductor (§7). Builds bundles + dispatches phase scripts; no script of its own. |
| `kitty-explore` | Inline; orchestrator-only graph queries → curated summary. Optional single librarian synthesis. |
| `kitty-impact` | Blast-radius bundle; librarian(impact) summarizes; tier by `blast_radius`. |
| `kitty-annotate` | Fetch pending → fan out `cartographing-kitten` batches → **run boundary: orchestrator `submit_annotations`** → repeat. Tier by `recommended_model_tier`. Worst 429-storm case → fallback bounded batches. |
| `kitty-brainstorm` | Research swarm: librarian(architecture)+librarian(pattern) parallel. |
| `kitty-plan` | Research fan-out (4 lenses) → orchestrator synthesis → plan file. Optional 2nd round for lens cross-talk. |
| `kitty-work` | **Main-loop loop of per-unit runs:** build unit bundle → implement (tier by unit) → two-gate self-review → **run boundary: re-index + graph_diff + validate_graph** → plan-state update via MCP → commit. Enforces produced-code LOC (flag-only, §12). |
| `kitty-review` | `pipeline(dimensions, review → adversarial-verify)`: always-on correctness+testing; conditional impact/structure/context; P0/P1 verified at opus/xhigh before reporting. |
| `kitty-lfg` | Sequential plan → work → review, pipeline mode (no prompts). One run-id; phases append the journal strictly sequentially. Satisfies the "no work without approved plan" gate via its own plan phase + auto-approve-recommended. |

**Two-gate review** (spec-compliance ∧ code-quality) and **verification before
completion** (fresh evidence run captured in the journal — tests/validators **and** the
per-unit `graph_diff`/`validate_graph` output) apply throughout.

---

## 10. Cross-session continuation — plan-state is the sole authority

### 10.1 Ship plan-state in the package (fixes the distribution gap)
`scripts/plan_status.py` + `scripts/plan_state.py` live outside `src/cartograph` and are
**not** shipped (the wheel packages only `src/cartograph`; the plugin runs `uvx
cartographing-kittens`). Fix:

1. Move the state **library** → `src/cartograph/planning/state.py` (parse / serialize /
   mutate / validate / rollup). Now it ships.
2. Add MCP tools in `src/cartograph/server/tools/plan.py` (same `@mcp.tool()` pattern):
   `plan_create`, `plan_status` (read rollup + per-unit states), `plan_set_unit_state`,
   `plan_set_status`, `plan_audit`. The orchestrator mutates plan-state via these
   (consistent with "orchestrator is sole MCP client").
3. `scripts/plan_status.py` becomes a thin CLI shim over `cartograph.planning.state` for
   this repo's pre-commit audit + `/kitty-plans` dashboard.
4. Expose `cartographing-kittens plan audit` as a CLI subcommand for end-user pre-commit
   (git hooks can't call MCP). **Single source of truth, three front-ends.**

### 10.2 Plan-state is the only durable resume source (C10)
Plan-state (`docs/plans/*.md`, **git-tracked**) is idempotent: `**State:** complete —
implemented in <hash>` + frontmatter `implemented_in`. The run journal lives under
`.pawprints/runs/` which is **git-ignored** (disposable, like `graph.db`) — it cannot
survive a fresh clone, another machine, or a `.pawprints` clean.

> **Resume MUST be correct from plan-state alone.** Completed units come from plan-state
> body `**State:**` lines (via `plan_status`), never from the journal. The journal is a
> best-effort working-context cache read opportunistically *when present in the same
> working tree*; resume logic never branches on whether a journal exists.

### 10.3 Run identity & selection (C11)
- `<run-id> = <plan-slug>-<UTC-yyyymmddThhmmssZ>-<6char>` (sortable, collision-free,
  plan-derived). Plan-less phases (explore/impact) use a `phase-` prefix.
- `args.json` and the journal header record the absolute `plan_path` (the missing run→plan binding).
- Resume selects the run dir whose `plan_path` matches the plan being resumed; among
  matches, the lexically-greatest run-id (UTC timestamp ⇒ lexical == newest); else fresh.
- The Workflow tool's `resumeFromRunId` is a **separate intra-session** mechanism; on
  cross-session resume the orchestrator **ignores recorded workflow run IDs (dead)** and
  rebuilds from plan-state: any unit not `complete`-with-commit is re-dispatched fresh.

### 10.4 Plan-state write safety (C12)
Implemented in `cartograph.planning.state` (and therefore in the CLI shim + MCP tools):
1. **Atomic write:** temp-file-in-same-dir + `os.replace` (never a half-written plan).
2. **Optimistic concurrency guard:** capture content hash/mtime at parse; re-read
   immediately before replace; abort with a clear non-zero result if changed since parse
   (turns a silent last-writer-wins clobber into a loud, retryable failure; also prevents
   the whole-file rewrite from reverting a concurrent body edit).
3. **Single-writer discipline:** exactly one run may mutate a given plan at a time —
   `kitty`/`lfg` take an advisory lock `.pawprints/runs/<plan-slug>.lock` at run start and
   refuse/prompt if held; a fresh-context resume checks for a live lock before dispatching.
4. The orchestrator treats any non-zero `plan_set_*`/audit result as a **hard failure** —
   it does not append the journal or claim progress unless the mutation returned success.

A pytest asserts a mutation aborts when the file changed underneath it.

---

## 11. Generators, validators, tests

- **`_source/agents/*.yaml`** gains `lens` defs (consolidated librarian), `default_model`,
  `default_effort`; MCP tools removed from allowlists.
- **`_source/skills/*.yaml`** gains `orchestration_script` + `dispatch_policy` pointers and an `entry_self_check` block.
- **`generate_agents.py` / `generate_skills.py`** updated; the Codex output path + `agent.codex.toml.j2` removed.
- **New `scripts/test_orchestration_scripts.py`:** stubs the workflow globals
  (`agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `budget`) and executes every
  `*.orch.js` to assert: parses; control flow returns; args prologue present; no
  `scriptPath`/`name`; concurrency within cap; **and a failed/empty/schema-invalid
  `agent()` result is recorded as `failed`, never dropped** (§6).
- **`validate_skills.py`** keeps the existing ≤500-line skill-body cap (unchanged) and
  gains: required args prologue
  `const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})` (#68969); no
  `scriptPath`/`name` reliance (F2); each gated skill contains its entry self-check (§7);
  spawn-map = **exact** 7-agent roster match (rewritten from the current coverage check),
  run **after** regen so the manifest reflects the roster; precise unfenced trigger-word
  audit (#63725) scoped to the confirmed token only.

---

## 12. LOC discipline

The strict cap targets **harness-produced code** — what `kitty-work` writes in the
user's repo — not the framework's own files. (This was the original intent of the "no
file with excessive LOC ever" goal.)

**Framework files** keep the **existing convention**: SKILL.md bodies stay under ~500
lines with detail pushed to `references/` (already enforced by `validate_skills.py` and
stated in CLAUDE.md). No tighter cap is imposed — and the bundle-handoff rewrite tends to
*shrink* skill bodies anyway by relocating MCP choreography to the orchestrator. This
dissolves the C13 feasibility concern: orchestrating skills are free to carry the
hardening + orchestration prose they need.

**Harness-produced code** (`kitty-work` output): soft **300** / hard **400** physical
lines per file (comments counted, blank-only excluded; generated + vendored exempt by a
config glob; tests split by behavior group). Enforced by a three-layer discipline, in
priority order:

1. **Design-time modularity (primary).** `kitty-work` plans file boundaries *before*
   writing each unit and produces well-factored files that stay under the soft cap.
   Staying under the cap is the worker's responsibility, not an afterthought — this is
   just "write modular code," and aligns with Goal 6 (best SWE patterns).
2. **Hard cap = tripwire.** If a unit's implementation would push a file over 400 lines,
   the worker splits at a seam it identified at design time; if no clean seam exists it
   **stops and surfaces the decision**. It never silently exceeds the cap and never
   forces an awkward seam to satisfy a number.
3. **Review backstop.** `expert-kitten-structure` raises a finding on any file over the
   cap — catching anything the worker missed.

This is stronger than reactive flag-only (the worker is *responsible* for the cap by
design) and safer than blind post-hoc auto-rewrite (no surprise refactors smuggled into
a unit).

---

## 13. Mechanism validation (the Unit 0 gate) — partially done

The inline-script mechanism was **exercised live** during this design (the red-team ran
as a `Workflow({script, args})` dispatch of 25 agents). That run **proved:** the inline
`script:` param exists and runs (F2); `args` as an object + the JSON.parse prologue work;
`agent({schema})` enforces structured output (we received schema-clean JSON);
`agent({model, effort})` calls are accepted; and `agent()` inside a script genuinely
spawns and returns (not a nested-subagent no-op, #19077).

**Model routing → RESOLVED (Unit 0, 2026-06-18):** the `_probe.orch.js` probe spawned
haiku/sonnet/opus agents that reported `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`,
and `claude-opus-4-8[1m]` respectively — distinct, tier-matching ids. **`agent({model})`
genuinely routes; #43869 does not extend to the Workflow resolver.** §4 stands; Goal 3
is intact; no demotion. (Had the children all reported the session model, the gate would
have demoted §4 to advisory and struck model-tier routing before building units 5–8.)
See `docs/plans/notes/2026-06-18-unit0-mechanism-gate.md`.

---

## 14. Codex removal

Delete `plugins/kitty/.codex/**`, the Codex branches of `generate_commands.py` /
`generate_agents.py`, `_source/templates/agent.codex.toml.j2`,
`docs/architecture/codex-workflow-contract.md`, and any `.codex-plugin/` manifest. Strip
dual-runtime language from `CLAUDE.md`, `_source/manifests/plugin.yaml`, and
`docs/architecture/repo-boundaries.md`.

---

## 15. Memory integration

The bundle carries an explicit **"Memory lessons (litter/treat)"** section the
orchestrator populates from `query_litter_box`/`query_treat_box` (step 2); agent prompts
must apply it. The existing `memory-workflow.md` preflight/postflight is reconciled: the
**preflight query** is the orchestrator's bundle step; the **postflight write**
(`add_litter_box_entry`/`add_treat_box_entry`) is a main-loop step after the run (a run
boundary — MCP-only). Agents never touch memory directly.

---

## 16. Testing strategy

1. Generator round-trip (`--check`) for agents/skills/manifests.
2. `validate_skills.py` with the new LOC + script + self-check + exact-roster rules.
3. `test_orchestration_scripts.py` (§11) — control flow, prologue, no-name/scriptPath,
   concurrency cap, **and partial-failure handling**.
4. **Mechanism gate** (Unit 0, §13) — the model-routing go/no-go probe.
5. **Fallback enforcement test** (not just input parity): a negative fixture where an
   agent returns schema-invalid output; assert the fallback **rejects + re-dispatches**,
   then journals a failure after the bounded retry — and that dedup prevents
   double-dispatch and the concurrency cap holds.
6. **Path-selection test:** a disabled/version-gated Workflow routes to the fallback;
   a mid-run Workflow failure does not double-dispatch completed items.
7. **Plan-state safety test:** a mutation aborts when the file changed underneath it.
8. Existing `pytest` suite stays green; CI matrix unchanged (3.13–3.14).

---

## 17. Rollout (single cycle, decomposable into plan units)

0. `cartograph.planning` module + `plan.py` MCP tools + write-safety; `dispatch-policy.md`
   + `bundle-format.md` references; **`_probe.orch.js` + the §13 model-routing gate.**
1. Schema + generator/validator updates; exact-roster spawn-map; produced-code LOC checks.
2. Agent roster: consolidate librarian, strip MCP, slim experts, annotator run-boundary.
3. Shipped `*.orch.js` + harness + live smoke test of the **first real** script.
4. `kitty` conductor + redundant phase self-checks.
5. Rewrite plan / work / review / lfg.
6. Rewrite explore / impact / annotate / brainstorm.
7. Codex removal + CLAUDE.md/docs updates + plan-migration handling.
8. Full regen; green CI.

**Plan migration:** a plan with no journal is treated as fresh (unit state derived from
plan-state alone); old plans' embedded orchestration prose is inert under the conductor;
listed as an explicit risk.

---

## 18. Risk register

| Risk | Status / mitigation |
|------|---------------------|
| **F1 — `agent({model})` routing in the Workflow runtime** | **RESOLVED (Unit 0, §13): VERIFIED real** — probe agents reported distinct tier-matching model ids. §4 stands; no demotion. (Task/fallback path routing remains broken, as designed-around.) |
| Workflow availability unknowable at author time (F3) | Shared fallback + `auto` probe selection (§5.3). Value is materially better for paid+enabled users; documented honestly. |
| Inline `script:` param existence | **VALIDATED** in this runtime (§13). Still gated behind the Unit 0 probe for the target environment. |
| Fallback coordination is prose, not a scheduler | Bounded by design (§5.2); storm protection is explicitly Workflow-path-only and NOT claimed for the fallback; manual-verification checklist + tests (§16). |
| Workflow-agent MCP may work (docs claim ToolSearch) | Baseline assumes it does **not**; a future enhancement may let workflow-librarians do optional MCP top-ups once validated. |
| Inline-script context cost | Run-level bound = (distinct phase scripts in run) × ≤200 lines (e.g. lfg ≈ 3×200 ≈ 600, one-time); per-unit/per-dimension loops run inside one run and do not multiply it. A small fixed constant vs `bundle.md`. |
| Concurrent runs on one plan | Advisory lock + optimistic guard (§10.4); resume checks the lock first. |
| Plan migration of in-flight plans | §17 migration rule; explicit risk. |
