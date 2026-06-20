# Dispatch Policy — Complexity Tiering

The single source of truth for how each dispatched item is routed to a
`(model, effort)` tier. Orchestration scripts and skills point here; they never
hard-code the rubric.

## Who computes the tier

The **main-loop orchestrator** (the sole MCP client) computes a complexity class
per item from graph signals it already holds, resolves it to a `(model, effort)`
pair, and passes the resolved pairs to the dispatch script as `args.tiers`.

> **The orchestration script does NOT classify.** It receives `args.tiers` —
> a map from item id to a resolved `{model, effort}` — and only *applies* it on
> each `agent(prompt, {model, effort, ...})` call. The rubric below lives here so
> scripts stay rubric-free and the policy is versioned in exactly one place.

The orchestrator computes tiers in step 4 of the data flow (see
`bundle-format.md`), after building the bundle and before building `args`.

## Signals

The orchestrator scores each item from these signals, all already available from
the graph context it gathered while building the bundle:

| Signal | Source | Meaning |
|---|---|---|
| `nodes_in_scope` | bundle Target nodes | how many graph nodes the item touches |
| `max_centrality` | cached weighted-PageRank `centrality` field | structural importance of the most central node in scope |
| `files_touched` | unit / diff file list | number of distinct files the item spans |
| `blast_radius` | `find_dependents` transitive count | downstream nodes affected by the change |
| `bundle_section_tokens` | size of the item's bundle section | how much context the agent must digest |
| `finding_severity` | review finding `severity` (verify stage only) | `P0`/`P1`/`P2`/`P3` of a finding being adversarially verified |

`max_centrality` reads the cached centrality value (refreshed lazily on first
read after the graph changes); the orchestrator does not recompute it.

## Tiering table

| Class | Predicate | model · effort |
|-------|-----------|----------------|
| **trivial** | `nodes ≤ 1` ∧ `max_centrality < 0.1` ∧ `files == 1` ∧ no public API ∧ `section_tokens < 1000` | `haiku` · low |
| **hard** | `files ≥ 3` ∨ `blast_radius ≥ 15` ∨ `max_centrality ≥ 0.5` ∨ architectural/new-file ∨ verify of `P0`/`P1` | `opus` · high (`xhigh` for hardest verify) |
| **standard** | otherwise | `sonnet` · medium |

Evaluate **trivial** first, then **hard**; anything that matches neither falls to
**standard**. The hardest-verify case — adversarial verification of a `P0`/`P1`
review finding — uses `opus · xhigh`; all other `hard` items use `opus · high`.

## Path asymmetry — where tiering actually takes effect

Tiering resolves to a `(model, effort)` pair on **both** dispatch paths, but the
runtime only honors it on one of them.

- **Workflow path — real, VERIFIED.** `agent(prompt, {model, effort})` genuinely
  routes the child model. The Unit 0 mechanism gate spawned haiku/sonnet/opus
  probe agents that each reported a distinct, tier-matching model id
  (`claude-haiku-4-5-…`, `claude-sonnet-4-6`, `claude-opus-4-8[1m]`). The
  Workflow `agent()` resolver is exempt from the broken-model-selection bug
  ([#43869](https://github.com/anthropics/claude-code/issues/43869)). Effort is
  a real runtime knob on this path.

- **Task fallback path — advisory only.** Per-subagent model selection is broken
  on the Task path (#43869): every spawned agent resolves to the parent model
  regardless of the requested `model`. On this path the resolved tier is
  **recorded for forward-compatibility only — no runtime effect today.** Effort
  is conveyed to the agent as a **prompt hint** (a best-effort proxy, not the
  runtime knob). The orchestrator still computes tiers identically so the
  contract is symmetric and the fallback upgrades for free if/when #43869 is
  fixed.

> **Net:** smart model-tier routing and runtime effort control are a genuine
> benefit on the Workflow path and a no-op-but-harmless record on the Task
> fallback. Scripts request `{model, effort}` the same way regardless; only the
> runtime differs. When the Unit 0 verdict for a target environment is `no-op`,
> scripts omit `model` and pass `effort` as a prompt hint only.

## What scripts must do with `args.tiers`

- Look up `args.tiers[itemId]` and pass its `{model, effort}` straight into the
  `agent(...)` call for that item.
- Never derive a tier from the signals themselves — the orchestrator already did.
- If an item has no entry in `args.tiers`, default to `sonnet · medium`
  (the **standard** tier) rather than guessing from signals.
