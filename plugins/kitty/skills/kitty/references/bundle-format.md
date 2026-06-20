# Context Bundle Format

The **Context Bundle** is the single curated file the orchestrator hands every
dispatched agent. It *is* the graph-as-context: the orchestrator gathers all
structural intelligence via MCP, distills it into one markdown file, and the
agent reads exactly that file. Agents never call MCP and never explore the
codebase at large.

## Location & transport

- The orchestrator writes one bundle per run to
  `.pawprints/runs/<run-id>/bundle.md`.
- The orchestrator passes the agent an **absolute** `bundlePath` inside `args`.
- Per [#63102](https://github.com/anthropics/claude-code/issues/63102) (no
  byte-exact arg transport), keep `args` **small and quote-light** — paths and
  ids only. All large or formatted context lives in `bundle.md`, **never** in
  `args`. The bundle is the payload; `args` is just the pointer plus item ids
  and resolved tiers.

> `.pawprints/runs/` is git-ignored and disposable. The bundle is working
> context for a single run, not a durable artifact — durable resume comes from
> git-tracked plan-state, not the bundle.

## Sections

The bundle is one markdown document with these sections, in this order. The
orchestrator includes the sections relevant to the dispatch; each agent reads
**one** section appropriate to its lens/role (plus targeted source lines only to
verify a specific claim).

### 1. Target nodes
The nodes in scope for this item — qualified names, kinds (`module`/`class`/
`function`/`method`/`variable`), roles, tags, summaries, and file/line ranges.
For a review this is the changed set; for research/plan it is the feature-area
search results; for work it is the unit's file list.

### 2. File structures
Per key file: the node listing (`get_file_structure`) with kinds, summaries,
tags, and roles, so the agent understands module organization without reading
whole files.

### 3. Key symbols
Metadata + 1-hop neighbor relationships (`imports`, `calls`, `inherits`,
`contains`, `depends_on`) for the most important symbols in scope, from
`query_node` / `batch_query_nodes`.

### 4. Dependencies
Transitive upstream dependencies (what the target area needs), grouped by depth
with role/tag annotations — from `find_dependencies`.

### 5. Dependents
Transitive downstream dependents / blast radius (what depends on the target
area), grouped by depth with role/tag annotations — from `find_dependents`.

### 6. Memory lessons (litter/treat)
Lessons the orchestrator pulled from the persistent memory boxes via
`query_litter_box` / `query_treat_box` (the preflight half of the
`memory-workflow.md` contract). Agent prompts **must apply** these.

```
## Memory lessons (litter/treat)

### Litter lessons to avoid
- `[anti-pattern]` <one specific lesson>
  Context: <files / symbols / error text>

### Treat lessons to follow
- `[convention]` <one specific lesson>
  Context: <files / symbols>

### Memory gaps
- No relevant entries found for "<term>"
```

Agents never touch memory directly — they only read this section. The
postflight write (`add_litter_box_entry` / `add_treat_box_entry`) is a
main-loop step after the run (a run boundary; MCP-only).

## Agent prologue contract (mandatory)

Every agent's prompt begins with a bundle-read assertion. Before doing any
analysis the agent MUST:

1. `Read` the file at the absolute `bundlePath` it was given.
2. Assert the file is **readable and non-empty**.
3. If the read fails or the file is empty, **stop** and return the envelope
   `{"status": "bundle_unreadable", ...}` — do nothing else, attempt no MCP, and
   do not fabricate analysis from the prompt alone.

This guarded `Read` of the session-local run directory is the **only** file read
agents perform by default (plus targeted source lines to verify a specific
claim). It is pre-authorized in the skill `allowed-tools`. Agents do **not**
call MCP and do **not** explore the codebase.

## Return envelope `status`

Every agent return carries a mandatory `status` field:

| `status` | Meaning | Orchestrator action |
|---|---|---|
| `ok` | Bundle read; analysis complete. | Reconcile the result normally. |
| `bundle_unreadable` | Bundle missing/empty/unreadable at `bundlePath`. | Treat as a failed item (re-dispatch within the §6 ledger budget, or gate). |
| `needs_more_context` | Bundle read, but a specific piece of context is missing. | Fetch it via MCP (a run boundary), then re-dispatch **once** with enriched context. |

`needs_more_context` returns to the orchestrator because expansion requires MCP
— that is a run boundary. The orchestrator fetches the requested context, writes
an enriched bundle section, and re-dispatches the agent (**max one** follow-up
pass per item; the expansion counts against the item's single-expansion budget).

The full envelope shape (`agent`, `role`, `findings_or_observations`, `summary`,
`confidence`, `sources`, plus this `status`) is specified in
`agent-output-contract.md`.

## Why this shape

The bundle is the graph-as-context and the only thing agents read, so agents
stay MCP-free (dodging the empty-subagent-MCP-registry limitation) and the
topology stays flat (no nested subagents). Keeping `args` to a pointer plus ids
sidesteps the arg-transport bugs, and the prologue assertion makes a missing
bundle a clean `bundle_unreadable` return instead of a silent hallucination.
