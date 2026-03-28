---
name: cartograph:annotate
description: >
  Annotate codebase nodes with summaries, tags, and roles to enable semantic search.
  Use when the user asks to "annotate the codebase", "enrich the graph", "enable
  semantic search", "add summaries", "tag nodes", or when annotation_status shows
  many pending nodes. Also use when search results are poor because nodes lack summaries.
---

# Cartograph: Annotate

Enrich the Cartograph graph with human-readable summaries, semantic tags, and role
descriptions so that `search` returns meaningful results for domain queries.

## When to use

- After initial indexing when `annotation_status` shows pending nodes
- When `search` results are poor or empty despite the graph being indexed
- When the user wants semantic search ("find auth code", "what handles payments")
- Proactively after large code changes to keep the graph enriched

## Workflow

### 1. Check status

Call `annotation_status()` to see how many nodes are pending, annotated, and failed.
If `pending` is 0, annotation is complete.

### 2. Get a batch

Call `get_pending_annotations(batch_size=10)` to receive nodes with:
- Source code and file context
- Neighbor information (what calls/imports the node)
- The seed taxonomy of suggested tags

### 3. Generate annotations

For each node, read the source code and context, then produce:

- **summary** (str): One specific sentence. "Validates JWT tokens and extracts user claims"
  is better than "Handles validation".
- **tags** (list[str]): Use seed taxonomy when it fits, create new tags when needed.
  Good tags: domain ("authentication"), layer ("middleware"), pattern ("factory").
- **role** (str): The node's job title. "Request handler", "Data access layer",
  "Input validator", "Configuration manager".

If a node is too complex or ambiguous to annotate confidently, set `failed: true`.

### 4. Submit

Call `submit_annotations(annotations=[...])` with the generated annotations.

### 5. Repeat

Loop steps 2-4 until `annotation_status` shows `pending: 0`.

## Parallel processing for large codebases

For codebases with **50+ pending nodes**, use parallel subagents:

1. Check total pending count with `annotation_status`
2. Spawn 2-3 `cartograph-annotator` agents, each processing its own batch
3. Each agent independently calls `get_pending_annotations` → generates → `submit_annotations`
4. Batches don't overlap — the server tracks which nodes are pending

See the `cartograph-annotator` agent definition for the subagent contract.

## Seed taxonomy

Use these tags when they fit, but don't force them:

`authentication`, `database`, `api`, `validation`, `configuration`, `middleware`,
`service`, `model`, `controller`, `utility`, `testing`, `error-handling`,
`caching`, `logging`, `serialization`, `formatting`, `parsing`, `io`

Create new tags for domain-specific concepts (e.g., "payment-processing", "websocket").

## Quality guidance

- **Be specific** — "Formats datetime to ISO 8601" beats "Formatting utility"
- **Use neighbor context** — understanding callers helps summarize accurately
- **Skip trivial nodes quickly** — simple getters/constants need only terse summaries
- **Mark uncertain nodes as failed** — better to retry than to pollute the graph

## Tips

- Start with `batch_size=10`, adjust based on node complexity
- Run annotation after major code changes to keep semantic search accurate
- See `references/annotation-workflow.md` for the detailed workflow guide
- See `references/tool-reference.md` for full parameter details
