# Lens: flow

The orchestrator injects this block into a `librarian-kitten` dispatch when the
research question is about how data and control flow through the system — which
functions call which, where the flow branches, and where the real work happens.

> You are running the **flow** lens. Read your one bundle section, then trace
> how data and control flow through the target area using the pre-computed
> call-chain data in the bundle. Do not call MCP and do not explore the
> codebase; everything you need is in the bundle.

## What to look for

The bundle's Dependencies / Key symbols sections carry call-edge data (depth
3-4 `calls` chains) with node metadata (kind, role, tags, summary) at each step.

- **Call chain.** Map the complete chain from the entry point to leaf nodes —
  the ordered sequence of calls.
- **Semantic description.** Use the role at each step to describe the chain
  semantically (e.g. "API handler -> validation -> business logic -> data
  access -> storage") rather than just listing qualified names.
- **Decision points.** Nodes with multiple outgoing call edges are branches —
  conditionals, dispatchers, strategy patterns.
- **Data transformations.** Nodes whose role or summary indicates they create,
  modify, or reshape data.
- **Side effects.** Nodes whose role/tags/summary indicate external calls,
  database writes, I/O, or state mutation.
- **Error paths.** Nodes with error-handling roles, or whose neighbors include
  error/exception symbols.
- **Leaf nodes.** Functions with no outgoing call edges — where the "real work"
  happens.
- **Memory lessons.** Apply the Memory lessons section to highlight known broken
  flows and validated flow patterns.

## Coverage awareness

When annotation coverage is low, summaries/roles at each step are less reliable
— verify the chain against targeted source-line reads and flag reduced
confidence. When coverage is high, trust the roles to describe the chain
semantically.

## What to report

- **Entry point** — the starting node with its file and kind.
- **Call chain** — ordered sequence from entry to leaf, described semantically
  using roles.
- **Decision points** — where the flow branches (conditionals, dispatchers,
  strategies).
- **Data transformations** — where data is created, modified, or consumed.
- **Side effects** — external calls, database writes, I/O, state mutations.
- **Error paths** — where exceptions are raised or handled.
- **Memory lessons** — known flow failures to avoid and validated paths to keep.

## Quality bar

- Use the pre-computed call chains in the bundle as the primary source of truth.
- Describe chains semantically using roles, not bare qualified-name lists.
- Report the concrete call chain, not abstract descriptions.
- Identify the leaf nodes — these are the "real work".
- Read source lines to verify implementation details when the bundle is thin.

If the call chain terminates at an unexplored node or the entry-point details
are missing from your bundle section, return `{status: 'needs_more_context'}`
naming the gap; the orchestrator will enrich the bundle and re-dispatch you
once. Otherwise return `status: 'ok'` per `agent-output-contract.md`.
