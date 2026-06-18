---
title: Kitty Orchestration Rewrite
type: refactor
status: in_progress
date: 2026-06-18
origin: docs/superpowers/specs/2026-06-18-kitty-orchestration-rewrite-design.md
units:
  - id: 0
    title: Mechanism gate — model-routing probe (go/no-go)
    state: complete
    implemented_in: 033f81b
  - id: 1
    title: Planning package + MCP tools + write-safety + shims
    state: complete
    implemented_in: dd9fb7c
  - id: 2
    title: Source schema + generators + validators
    state: complete
    implemented_in: e043a2d
  - id: 3
    title: Policy & format references (dispatch-policy, bundle-format, lenses)
    state: complete
    implemented_in: af6a316
  - id: 4
    title: Agent roster — hybrid 7, MCP-free
    state: complete
    implemented_in: 70b18c4
  - id: 5
    title: Orchestration scripts + test harness
    state: pending
  - id: 6
    title: kitty conductor + redundant phase gates
    state: pending
  - id: 7
    title: Rewrite plan / work / review / lfg
    state: pending
  - id: 8
    title: Rewrite explore / impact / annotate / brainstorm
    state: pending
  - id: 9
    title: Codex removal, docs, full regen, green CI
    state: pending
---

# Kitty Orchestration Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax. Update unit `**State:**` lines ONLY via
> `uv run python scripts/plan_status.py set-unit <plan> <id> <state> [--commit HASH]` —
> never hand-edit. **Unit 0 is a hard gate: its outcome can rewrite Units 5–8.**

**Goal:** Replace the prose-driven skill/sub-agent orchestration with dynamic,
complexity-routed, parallel orchestration on the Workflow tool (graceful Task-tool
fallback), using a graph Context Bundle so agents never call MCP and never re-read the
codebase, with cross-session resume anchored in git-tracked plan-state.

**Architecture:** Main-loop orchestrator is the sole MCP client; it fetches graph
context, writes one curated Context Bundle, computes per-item `(model, effort)` tiers,
and dispatches one MCP-free fan-out per **run boundary** (workflow path) or a bounded
Task loop (fallback). Every MCP-gated step (expansion, re-index, annotation submit,
plan-state write) returns to the main loop. See the spec for the full rationale.

**Tech Stack:** Python 3.13–3.14, FastMCP (`@mcp.tool()`), tree-sitter, SQLite, `uv`,
Jinja2 generators, Claude Code Workflow tool (JS orchestration scripts).

## Global Constraints

- Python **3.13–3.14** (CI matrix); manage deps with `uv` only.
- Distributable code lives in `src/cartograph` (the wheel packages only this); the plugin
  runs `uvx cartographing-kittens`. Anything end users must run at runtime ships here —
  **never** under `scripts/` (repo-local dev only).
- MCP tools: register with `@mcp.tool()` in `src/cartograph/server/tools/*.py` and import
  the module in `src/cartograph/server/main.py` so the decorator fires. Skill/agent
  allowlists reference the fully-qualified name `mcp__plugin_kitty_kitty__<tool>`.
- Generated harness artifacts are edited via `plugins/kitty/_source/` only; run the
  matching `scripts/generate_*.py` after, never hand-edit generated files.
- Skill `name:` matches `^[a-z0-9-]{1,64}$`; skill body ≤ **500** lines (existing cap).
- Orchestration scripts: ≤ **200** lines; MUST begin with the args prologue
  `const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})`; MUST NOT use
  `scriptPath:` or `name:`.
- Harness-**produced** code (kitty-work output): soft **300** / hard **400** physical
  lines per file (comments counted, blank-only excluded; generated/vendored exempt).
- 7-agent roster: `librarian-kitten` (lens arch|pattern|flow|impact),
  `expert-kitten-{correctness,testing,impact,structure,context}`, `cartographing-kitten`.
- Agents are **MCP-free** (tools: Read, Grep, Glob [+ Bash for the annotator]).
- Qualified names use `::`; edge kinds `imports|calls|inherits|contains|depends_on`;
  node kinds `module|class|function|method|variable`.
- Verify gates: `uv run pytest`, `uv run ruff check src/`, `uv run ruff format --check src/`,
  `uv run basedpyright --level error`, `uv run python scripts/validate_skills.py`,
  `uv run python scripts/plan_status.py audit`.

## Spec → Unit traceability

| Spec section | Unit(s) |
|---|---|
| §13 mechanism gate (model routing) | 0 |
| §10 plan-state shipped + write-safety | 1 |
| §11 schema/generators/validators | 2 |
| §4 dispatch policy, §3 bundle format, §8 lenses, §15 memory | 3 |
| §8 agent roster (hybrid, MCP-free), §8 annotator run-boundary | 4 |
| §3/§5/§6 orchestration scripts + harness | 5 |
| §7 conductor + redundant gates | 6 |
| §9 rewrite plan/work/review/lfg | 7 |
| §9 rewrite explore/impact/annotate/brainstorm | 8 |
| §14 Codex removal, §17 regen/CI, §12 LOC, migration | 9 |

## Plan-shape note (why Units 5–8 are scoped, not pre-coded)

Unit 0 resolves whether `agent({model})` actually routes (§13/F1). If it is a no-op,
§4 model-tiering is demoted to advisory and the conductor/skill scripts change. Writing
the final 200-line orchestration scripts and full SKILL.md rewrites **before** that gate
would be premature. So Units 0–5 carry complete, TDD-level detail; Units 6–8 carry exact
files, interfaces, structural requirements, and the precise validation gate that defines
"done" — their authored prose is produced at execution against the spec and the Unit 0
outcome. This is a deliberate sequencing decision, not deferred detail: every unit states
exactly what to build and how to prove it.

---

### Unit 0 — Mechanism gate — model-routing probe (go/no-go)

**State:** complete — implemented in 033f81b

The whole "smart dispatch" value rests on the unverified assumption that the Workflow
runtime's `agent({model})` is exempt from #43869. This run already proved inline
`script`/`args`/`schema` and `agent()` spawning work; only model routing is unconfirmed.
This unit confirms or refutes it **before** any model-tiering work is built.

**Files:**
- Create: `plugins/kitty/skills/kitty/references/workflows/_probe.orch.js`
- Create: `docs/plans/notes/2026-06-18-unit0-mechanism-gate.md` (record the verdict + evidence)

**Interfaces:**
- Produces: a recorded verdict `model_routing ∈ {real, no-op}` consumed by Units 5–8 and
  by the §4 demotion decision.

- [ ] **Step 1: Write the probe script** (`_probe.orch.js`)

```javascript
export const meta = {
  name: 'kitty-probe',
  description: 'One-time probe: does agent({model}) actually route the child model?',
  phases: [{ title: 'Probe' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})
const SCHEMA = {
  type: 'object', required: ['reported_model', 'evidence'], additionalProperties: false,
  properties: { reported_model: { type: 'string' }, evidence: { type: 'string' } },
}
const ask = 'State your exact underlying model id (e.g. claude-haiku-4-5, claude-opus-4-8). '
  + 'Then in one sentence give any evidence you can about which model you are. Return per schema.'
phase('Probe')
const tiers = ['haiku', 'sonnet', 'opus']
const out = await parallel(tiers.map((m) => () =>
  agent(ask, { label: `probe:${m}`, phase: 'Probe', schema: SCHEMA, model: m })
    .then((r) => ({ requested: m, ...r }))))
return { results: out.filter(Boolean) }
```

- [ ] **Step 2: Run the probe** via the Workflow tool with `{ script: <_probe.orch.js contents>, args: {} }`.
  Expected: three results. **Interpretation:** if `reported_model` tracks `requested`
  (haiku≠opus), routing is **real**. If all three report the same id (the session model),
  routing is a **no-op** under #43869.

- [ ] **Step 3: Record the verdict** in `docs/plans/notes/2026-06-18-unit0-mechanism-gate.md`:
  the three results verbatim, the verdict, and the consequence.

- [ ] **Step 4: Apply the gate.** If **no-op**: edit the spec §4 to "advisory on both
  paths", strike model-tier routing from Goal 3, and add a note to Units 5–8 that scripts
  pass `effort` hints only (no `model`). If **real**: proceed unchanged. Commit the note +
  any spec edit.

- [ ] **Step 5: Commit & mark unit complete**

```bash
git add plugins/kitty/skills/kitty/references/workflows/_probe.orch.js docs/plans/notes/2026-06-18-unit0-mechanism-gate.md
git commit -m "test(orchestration): model-routing mechanism gate (Unit 0)"
uv run python scripts/plan_status.py set-unit docs/plans/2026-06-18-001-refactor-orchestration-rewrite-plan.md 0 complete --commit "$(git rev-parse --short HEAD)"
```

---

### Unit 1 — Planning package + MCP tools + write-safety + shims

**State:** complete — implemented in dd9fb7c

Move plan-state into the shipped package, add atomic-write + optimistic-concurrency
safety, expose it as MCP tools, and keep the repo's CLI + pre-commit working via thin
shims. (Spec §10.)

**Files:**
- Create: `src/cartograph/planning/__init__.py`
- Create: `src/cartograph/planning/state.py` (moved from `scripts/plan_state.py` + safety)
- Create: `src/cartograph/planning/cli.py` (argparse: report/audit/set-unit/set-status)
- Create: `src/cartograph/server/tools/plan.py` (MCP tools)
- Modify: `src/cartograph/server/main.py` (import `tools.plan` so decorators register)
- Modify: `src/cartograph/__init__.py` or entry module (add `plan` subcommand to `main`)
- Modify: `scripts/plan_state.py` → thin re-export shim of `cartograph.planning.state`
- Modify: `scripts/plan_status.py` → thin shim delegating to `cartograph.planning.cli`
- Create: `tests/planning/test_state_safety.py`
- Create: `tests/server/test_plan_tools.py`

**Interfaces:**
- Consumes: existing `Plan`, `Unit`, `parse_plan`, `serialize_plan`, `set_unit_state`,
  `set_plan_status`, `validate`, `compute_rollup` (preserve signatures during the move).
- Produces (MCP tools, names used by Units 6–8):
  - `plan_create(path: str, title: str, type: str, units: list[dict]) -> dict`
  - `plan_status(path: str) -> dict` (rollup + per-unit states)
  - `plan_set_unit_state(path: str, unit_id: int, state: str, commit: str|None, reason: str|None) -> dict`
  - `plan_set_status(path: str, status: str, **kw) -> dict`
  - `plan_audit(path: str|None) -> dict`
- Produces (library): `state.write_plan_atomic(path, plan, expected_hash: str|None) -> None`
  raising `PlanConflictError` when `expected_hash` mismatches on-disk content.

- [ ] **Step 1: Move the module unchanged.** `git mv scripts/plan_state.py src/cartograph/planning/state.py`; add `src/cartograph/planning/__init__.py` re-exporting the public names. Run `uv run pytest` to confirm nothing imports the old path yet (fix imports in `scripts/plan_status.py` next step).

- [ ] **Step 2: Write the failing safety test** (`tests/planning/test_state_safety.py`)

```python
import hashlib
from pathlib import Path
import pytest
from cartograph.planning import state as st

PLAN = """---
title: T
type: feat
status: active
date: 2026-06-18
units:
  - id: 1
    title: U
    state: pending
---
# T — Plan
### Unit 1 — U
**State:** pending
"""

def _write(p: Path) -> Path:
    p.write_text(PLAN); return p

def test_atomic_write_uses_replace(tmp_path: Path):
    p = _write(tmp_path / "plan.md")
    plan = st.parse_plan(p)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    st.set_unit_state(plan, 1, "complete", commit="abc1234")
    st.write_plan_atomic(p, plan, expected_hash=h)
    assert st.parse_plan(p).units[0].state == "complete"

def test_optimistic_guard_aborts_on_concurrent_change(tmp_path: Path):
    p = _write(tmp_path / "plan.md")
    plan = st.parse_plan(p)
    stale = hashlib.sha256(b"different").hexdigest()
    st.set_unit_state(plan, 1, "complete", commit="abc1234")
    with pytest.raises(st.PlanConflictError):
        st.write_plan_atomic(p, plan, expected_hash=stale)
```

- [ ] **Step 3: Run it — expect FAIL** (`write_plan_atomic`/`PlanConflictError` missing): `uv run pytest tests/planning/test_state_safety.py -v`

- [ ] **Step 4: Implement `write_plan_atomic` + `PlanConflictError`** in `state.py`

```python
import hashlib, os, tempfile

class PlanConflictError(RuntimeError):
    """Raised when a plan file changed between parse and write."""

def write_plan_atomic(path, plan, expected_hash: str | None = None) -> None:
    if expected_hash is not None and path.exists():
        current = hashlib.sha256(path.read_bytes()).hexdigest()
        if current != expected_hash:
            raise PlanConflictError(f"{path} changed since parse; aborting write")
    text = serialize_plan(plan)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
```

- [ ] **Step 5: Run it — expect PASS**: `uv run pytest tests/planning/test_state_safety.py -v`

- [ ] **Step 6: Route CLI through the package.** Create `cartograph/planning/cli.py` holding the argparse from the old `plan_status.py` (report/audit/set-unit/set-status), with `cmd_set_unit`/`cmd_set_status` reading the file hash before parse and passing it to `write_plan_atomic` (treat `PlanConflictError` as a non-zero exit with a clear message). Make `scripts/plan_status.py` a 3-line shim: `from cartograph.planning.cli import main; raise SystemExit(main())`. Add a `plan` subcommand to the package console entry (`cartograph:main`) that calls `cli.main`.

- [ ] **Step 7: Write failing MCP-tool test** (`tests/server/test_plan_tools.py`) asserting `plan_status(path)` returns `{status, units:[{id,state}]}` and `plan_set_unit_state(path,1,"complete","abc1234",None)` flips the unit and is reflected by a re-read. Run — expect FAIL.

- [ ] **Step 8: Implement `src/cartograph/server/tools/plan.py`** with the five `@mcp.tool()` functions delegating to `cartograph.planning.state` (+ `write_plan_atomic`); import it in `server/main.py`. Run the test — expect PASS.

- [ ] **Step 9: Full gate + commit.** `uv run pytest`, `uv run ruff check src/`, `uv run basedpyright --level error`, `uv run python scripts/plan_status.py audit`. Commit; `set-unit ... 1 complete --commit`.

---

### Unit 2 — Source schema + generators + validators

**State:** complete — implemented in e043a2d

Extend the `_source` YAML schema and generators for the new model; tighten the validator
with the spec's new rules. (Spec §11.)

**Files:**
- Modify: `scripts/generate_agents.py` (new keys: `lens` set, `default_model`, `default_effort`; drop Codex output path)
- Modify: `scripts/generate_skills.py` (new keys: `orchestration_script`, `dispatch_policy`, `entry_self_check`)
- Modify: `scripts/validate_skills.py` (rules below)
- Modify: `plugins/kitty/_source/templates/agent.claude.md.j2` (model/effort defaults; tools without MCP)
- Delete: `plugins/kitty/_source/templates/agent.codex.toml.j2`
- Create: `tests/scripts/test_validate_orchestration.py`

**Interfaces:**
- Produces: validator functions `check_orch_prologue(path)`, `check_no_scriptpath(path)`,
  `check_entry_self_check(skill)`, `check_exact_roster(manifest)`; each returns `list[str]` errors.

- [ ] **Step 1: Write failing validator tests** (`tests/scripts/test_validate_orchestration.py`): an `.orch.js` missing the args prologue → error; one containing `scriptPath:` → error; one using `name:` → error; a gated skill body without its declared `entry_self_check` marker → error; a manifest with 6 or 8 agents → error (exact-roster=7). Run — expect FAIL.

- [ ] **Step 2: Implement the validator rules** in `validate_skills.py`:
  - `check_orch_prologue`: every `references/workflows/*.orch.js` must contain the exact
    prologue substring `typeof args === 'string' ? JSON.parse(args)`.
  - `check_no_scriptpath`: reject any `*.orch.js` containing `scriptPath:` or `name:` used
    as a Workflow input (regex on `Workflow(` arg or a top-level `scriptPath`/`name` key).
  - `check_orch_loc`: each `*.orch.js` ≤ 200 lines.
  - `check_entry_self_check`: each skill flagged `entry_self_check: required` must contain
    its self-check sentinel (e.g. a `<!-- entry-self-check -->` marker) in the body.
  - Rewrite `_validate_kitty_router_spawn_map` from coverage-check to **exact** match
    against the regenerated 7-agent `manifest.json` roster.
  - Keep the existing ≤500 skill-body cap unchanged.
  Run the tests — expect PASS.

- [ ] **Step 3: Update generators.** `generate_agents.py`: accept `lens` (list), `default_model`, `default_effort`; emit them into frontmatter; remove the `.codex/agents/*.toml` write + the codex template load. `generate_skills.py`: accept `orchestration_script`, `dispatch_policy`, `entry_self_check`; emit pointers into the SKILL.md. Keep `--check` drift detection.

- [ ] **Step 4: Gate + commit.** `uv run python scripts/generate_agents.py --check` (will fail until Unit 4 rewrites sources — acceptable here only if sources unchanged; otherwise run non-check to regenerate). `uv run pytest tests/scripts/ -v`; `uv run ruff check src/ scripts/`. Commit; `set-unit ... 2 complete`.

---

### Unit 3 — Policy & format references (dispatch-policy, bundle-format, lenses)

**State:** complete — implemented in af6a316

Author the shared reference docs every script and skill points at. (Spec §3, §4, §8, §15.)

**Files:**
- Create: `plugins/kitty/skills/kitty/references/dispatch-policy.md` (the §4 rubric + signals, ≤300 lines)
- Create: `plugins/kitty/skills/kitty/references/bundle-format.md` (Context Bundle layout, incl. the "Memory lessons" section, the agent bundle-read prologue contract, and the `bundle_unreadable`/`needs_more_context`/`ok` status envelope; ≤300 lines)
- Create: `plugins/kitty/skills/kitty/references/lenses/architecture.md`
- Create: `plugins/kitty/skills/kitty/references/lenses/pattern.md`
- Create: `plugins/kitty/skills/kitty/references/lenses/flow.md`
- Create: `plugins/kitty/skills/kitty/references/lenses/impact.md`
- Modify: `plugins/kitty/skills/kitty/references/agent-output-contract.md` (add `status` field; per-path schema-enforcement note from §5.2)

**Interfaces:**
- Produces: `bundle-format.md` defines the bundle section ids + the agent return envelope
  `{status: 'ok'|'bundle_unreadable'|'needs_more_context', ...}` consumed by Units 4–8.
- Produces: each `lenses/<lens>.md` is the prompt block the orchestrator injects for that
  librarian lens.

**Acceptance:** all six files exist, each ≤300 lines; `bundle-format.md` specifies the
absolute-`bundlePath` rule, the agent read-success prologue, the `status` envelope, and
the "Memory lessons (litter/treat)" section; `dispatch-policy.md` reproduces the §4 table
and signals verbatim. `uv run python scripts/validate_skills.py` passes.

- [ ] **Step 1:** Write `dispatch-policy.md` (copy the §4 table + signals; state that the
  **orchestrator** computes tiers and the script only applies `args.tiers`).
- [ ] **Step 2:** Write `bundle-format.md` (sections: Target nodes, File structures, Key
  symbols, Dependencies, Dependents, Memory lessons; the agent prologue contract; the
  status envelope; absolute-path rule per #63102).
- [ ] **Step 3:** Write the four `lenses/*.md` (port the four current librarian agent
  bodies into lens prompt blocks).
- [ ] **Step 4:** Update `agent-output-contract.md` with the `status` field + the §5.2
  fallback schema-enforcement note.
- [ ] **Step 5:** `uv run python scripts/validate_skills.py`; commit; `set-unit ... 3 complete`.

---

### Unit 4 — Agent roster — hybrid 7, MCP-free

**State:** complete — implemented in 70b18c4

Consolidate the librarians, strip MCP from all agents, slim the experts, and make the
annotator's write-back a documented run-boundary. (Spec §8.)

**Files:**
- Create: `plugins/kitty/_source/agents/librarian-kitten.yaml` (lens arch|pattern|flow|impact)
- Delete: `_source/agents/librarian-kitten-{researcher,pattern,impact,flow}.yaml`
- Modify: `_source/agents/expert-kitten-{correctness,testing,impact,structure,context}.yaml` (remove MCP tools; reference shared `agent-output-contract.md` + `bundle-format.md`; body ≤200 lines; `expert-kitten-structure` gains the produced-code oversized-file finding)
- Modify: `_source/agents/cartographing-kitten.yaml` (remove MCP; state that `submit_annotations` happens in the main-loop orchestrator after the batch — a run boundary)
- Regenerate: `plugins/kitty/agents/*.md` + `manifest.json` via `generate_agents.py`

**Interfaces:**
- Consumes: `references/bundle-format.md` + `references/lenses/*.md` (Unit 3).
- Produces: a 7-entry `manifest.json` roster (the exact set the Unit 2 validator enforces).

**Acceptance:** `generate_agents.py --check` passes; `manifest.json` lists exactly the 7
agents; no agent frontmatter `tools:` contains an `mcp__` entry; each agent body ≤200
lines; `validate_skills.py` passes (spawn-map exact-match).

- [ ] **Step 1:** Author `librarian-kitten.yaml` with a generic body that says "apply the
  lens-specific guidance provided in your task prompt" + the shared bundle-read + output
  contract; declare `lens: [architecture, pattern, flow, impact]`, `default_model: sonnet`.
- [ ] **Step 2:** Delete the four old librarian sources.
- [ ] **Step 3:** Edit the five expert sources: strip `mcp__*` tools (leave Read/Grep/Glob);
  point to shared references; add the oversized-file finding to `structure`.
- [ ] **Step 4:** Edit `cartographing-kitten.yaml`: strip MCP; document the submit run-boundary.
- [ ] **Step 5:** `uv run python scripts/generate_agents.py` then `--check`; `uv run python scripts/validate_skills.py`.
- [ ] **Step 6:** Commit; `set-unit ... 4 complete`.

---

### Unit 5 — Orchestration scripts + test harness

**State:** pending

Build the shipped `*.orch.js` scripts and the CI harness that executes them with stubbed
globals. (Spec §3, §5, §6, §11.)

**Files:**
- Create: `plugins/kitty/skills/kitty/references/workflows/{plan,work,review,annotate,impact,brainstorm}.orch.js`
- Create: `scripts/test_orchestration_scripts.py` (+ a tiny JS stub-runner via `node` if available, else a regex/AST static check)
- Create: `tests/scripts/test_orchestration_harness.py`

**Interfaces:**
- Consumes: `args` shape `{ bundlePath, items, tiers, lensRefs, dispatch }` (spec §3.2 step 5).
- Produces: each script exports `meta`, begins with the args prologue, fans out via
  `pipeline`/`parallel`, applies `args.tiers[item]` as `{model, effort}` (omit `model` if
  Unit 0 verdict was no-op), and records per-item `failed` status (spec §6).

**Acceptance:** `scripts/test_orchestration_scripts.py` asserts for every script: parses;
args prologue present; no `scriptPath`/`name`; ≤200 lines; a thrown/empty/schema-invalid
`agent()` result is recorded as `failed`, never dropped; concurrency within cap. The
harness runs in `uv run pytest` and (added in Unit 9) pre-commit.

- [ ] **Step 1: Write the harness** `test_orchestration_scripts.py`: define JS global stubs
  (`agent`, `parallel`, `pipeline`, `phase`, `log`, `args`, `budget`) where `agent` can be
  configured to throw / return empty / return schema-invalid; execute each `*.orch.js`
  (via `node --input-type=module` piping a prelude that defines the stubs, or a static
  check if `node` is unavailable) and assert control flow returns and failed items are
  recorded. Write the partial-failure assertion FIRST and watch it fail (no scripts yet).
- [ ] **Step 2: Author `review.orch.js`** (the heaviest): `pipeline(dimensions, review →
  adversarial-verify)`; always-on correctness+testing; conditional impact/structure/context;
  P0/P1 verified at the hard tier; per-item ledger + bounded retry. Keep ≤200 lines.
- [ ] **Step 3: Author `work.orch.js`, `plan.orch.js`, `annotate.orch.js`, `impact.orch.js`,
  `brainstorm.orch.js`** to the §9 shapes. `work.orch.js` handles ONE unit's intra-unit
  fan-out (the per-unit re-index/validate is a main-loop run boundary, not in-script).
- [ ] **Step 4:** Run `uv run pytest tests/scripts/test_orchestration_harness.py -v` — expect PASS; `uv run python scripts/validate_skills.py` (prologue/scriptPath/LOC rules).
- [ ] **Step 5:** Live smoke test of `review.orch.js` via the Workflow tool with a tiny fixture bundle; confirm it runs end-to-end. Record the result in the Unit 0 note file.
- [ ] **Step 6:** Commit; `set-unit ... 5 complete`.

---

### Unit 6 — kitty conductor + redundant phase gates

**State:** pending

Rewrite the `kitty` router into the conductor and add the redundant entry self-checks to
every phase skill. (Spec §7.)

**Files:**
- Modify: `plugins/kitty/_source/skills/kitty.yaml` (conductor: intent detect, gates, run-journal ownership, dispatch; `<!-- entry-self-check -->` not needed on the router itself)
- Modify: `_source/skills/kitty-{work,review,plan,brainstorm}.yaml` (add `entry_self_check: required` + the body self-check block per §7)
- Regenerate: skills via `generate_skills.py`

**Interfaces:**
- Consumes: `plan_status` MCP tool (Unit 1) for the work-gate check; `bundle-format.md`,
  `dispatch-policy.md` (Unit 3); the `*.orch.js` scripts (Unit 5).
- Produces: the run-id scheme `<plan-slug>-<UTC>-<6char>` + `.pawprints/runs/<run-id>/`
  layout (bundle.md, args.json, journal.md with `Plan:` header) used by all phase skills.

**Acceptance:** `validate_skills.py` passes incl. the `check_entry_self_check` rule for
work/review/plan/brainstorm and the exact spawn-map; `kitty.yaml` body ≤500 lines;
generated SKILL.md files match (`generate_skills.py --check`).

- [ ] **Step 1:** Rewrite `kitty.yaml`: conductor responsibilities, the run-boundary
  principle, path selection (`auto` probe, §5.3), run-id scheme + journal layout (§10.3),
  AskUserQuestion gating, and the Agent Spawn Map for the 7-agent roster.
- [ ] **Step 2:** Add the `entry_self_check` block to work/review/plan/brainstorm bodies
  (work: assert approved plan via `plan_status`; review: assert a diff exists; plan:
  confirm brainstorm output for net-new; each lazily attaches the run journal).
- [ ] **Step 3:** `generate_skills.py` then `--check`; `validate_skills.py`.
- [ ] **Step 4:** Commit; `set-unit ... 6 complete`.

---

### Unit 7 — Rewrite plan / work / review / lfg

**State:** pending

Rewrite the four heavy orchestrators to the bundle-handoff + run-boundary model with
superpowers hardening. (Spec §9.)

**Files:**
- Modify: `_source/skills/kitty-plan.yaml`, `kitty-work.yaml`, `kitty-review.yaml`, `kitty-lfg.yaml`
- Regenerate: via `generate_skills.py`

**Interfaces:**
- Consumes: Units 3–6 artifacts (references, roster, scripts, conductor, plan MCP tools).
- Produces: `kitty-work` writes plan-state via `plan_set_unit_state` and records the
  per-unit `graph_diff`/`validate_graph` evidence in the journal; `kitty-lfg` shares one
  run-id across plan→work→review, appending the journal strictly sequentially.

**Acceptance (the "done" gate for each skill):** body within ≤500; references the correct
`*.orch.js`; contains its entry self-check; two-gate review (spec-compliance ∧ quality)
present in review; `kitty-work` documents the post-write re-index run boundary and the
produced-code LOC discipline (§12); `validate_skills.py` + `generate_skills.py --check`
pass; no bare unfenced `workflow` trigger token (#63725 rule).

- [ ] **Step 1:** Rewrite `kitty-review.yaml` (dimensions, conditional reviewers, adversarial P0/P1 verify, dedup/synthesis, journal ledger). Verify against acceptance.
- [ ] **Step 2:** Rewrite `kitty-work.yaml` (per-unit main-loop loop; build unit bundle → implement → two-gate self-review → run-boundary re-index/validate → `plan_set_unit_state` → commit; produced-code LOC discipline).
- [ ] **Step 3:** Rewrite `kitty-plan.yaml` (research fan-out across 4 lenses → synthesis → plan file via `plan_create`).
- [ ] **Step 4:** Rewrite `kitty-lfg.yaml` (sequential, pipeline mode, shared run-id, satisfies the no-work-without-approved-plan gate via its own plan phase + auto-approve-recommended).
- [ ] **Step 5:** `generate_skills.py --check`; `validate_skills.py`; commit; `set-unit ... 7 complete`.

---

### Unit 8 — Rewrite explore / impact / annotate / brainstorm

**State:** pending

Rewrite the lighter skills to the same model. (Spec §9.)

**Files:**
- Modify: `_source/skills/kitty-explore.yaml`, `kitty-impact.yaml`, `kitty-annotate.yaml`, `kitty-brainstorm.yaml`
- Regenerate: via `generate_skills.py`

**Interfaces:**
- Consumes: Units 3–6 artifacts. `kitty-annotate` uses `annotate.orch.js` + the
  annotator run-boundary (`submit_annotations` in the main loop).

**Acceptance:** each body ≤500; references the correct script (where applicable); explore
and impact remain orchestrator-inline (optional single librarian synthesis); annotate
documents the submit run-boundary and tiers batches by `recommended_model_tier`;
`generate_skills.py --check` + `validate_skills.py` pass.

- [ ] **Step 1:** Rewrite `kitty-explore.yaml` (inline graph queries → curated summary).
- [ ] **Step 2:** Rewrite `kitty-impact.yaml` (blast-radius bundle; impact-lens librarian; tier by blast_radius).
- [ ] **Step 3:** Rewrite `kitty-annotate.yaml` (fan out batches → submit run-boundary loop).
- [ ] **Step 4:** Rewrite `kitty-brainstorm.yaml` (architecture+pattern lens research swarm).
- [ ] **Step 5:** `generate_skills.py --check`; `validate_skills.py`; commit; `set-unit ... 8 complete`.

---

### Unit 9 — Codex removal, docs, full regen, green CI

**State:** pending

Remove Codex, update docs, migrate in-flight plans, and prove the whole tree green.
(Spec §12, §14, §17.)

**Files:**
- Delete: `plugins/kitty/.codex/**`, `_source/templates/agent.codex.toml.j2`, `docs/architecture/codex-workflow-contract.md`, any `.codex-plugin/` manifest
- Modify: `CLAUDE.md` (drop dual-runtime + update Kittens-First to "orchestrator is sole MCP client"; document the new MCP plan tools + run-journal), `_source/manifests/plugin.yaml`, `docs/architecture/repo-boundaries.md`
- Modify: `generate_commands.py` / `generate_manifests.py` (drop Codex paths)
- Create: `docs/architecture/orchestration-model.md` (run boundaries, bundle handoff, dispatch paths — the canonical reference)

**Acceptance:** no `.codex` artifacts remain; `rg -i codex` finds only historical/changelog mentions; all generators `--check` clean; `uv run pytest`, `ruff check`, `ruff format --check`, `basedpyright --level error`, `validate_skills.py`, `plan_status.py audit` all pass; CLAUDE.md ↔ AGENTS.md parity holds (`sync_claude_agents_md`).

- [ ] **Step 1:** Delete Codex artifacts + strip Codex branches from generators.
- [ ] **Step 2:** Update CLAUDE.md, repo-boundaries, plugin manifest; add `orchestration-model.md`.
- [ ] **Step 3:** Plan migration: confirm old `docs/plans/*.md` still audit-clean; note their embedded orchestration prose is inert under the conductor (no edits needed).
- [ ] **Step 4:** Run every generator (non-check) then every `--check`; run the full gate suite.
- [ ] **Step 5:** Commit; `set-unit ... 9 complete`; then `set-status ... complete --implemented-in <merge-commit>` when the branch lands.

---

## Self-Review

- **Spec coverage:** every spec section maps to a unit (traceability table above). §13→0,
  §10→1, §11→2, §3/§4/§8/§15→3, §8→4, §3/§5/§6→5, §7→6, §9→7+8, §12/§14/§17→9.
- **Interface consistency:** MCP plan-tool names (`plan_create`, `plan_status`,
  `plan_set_unit_state`, `plan_set_status`, `plan_audit`) defined in Unit 1 and reused
  verbatim in Units 6–8. The args prologue string and `{status: ...}` envelope are defined
  in Units 2–3 and referenced unchanged downstream. Run-id scheme defined in Unit 6.
- **Gate dependency:** Unit 0 precedes all model-tiering work; its no-op branch is wired
  into Units 5–8 (omit `model`, keep `effort`).
- **Known approximation:** Units 6–8 are scoped-with-acceptance rather than pre-coded
  prose, by deliberate sequencing (see the plan-shape note) — each still states exact
  files, interfaces, and the validation command that defines "done".
