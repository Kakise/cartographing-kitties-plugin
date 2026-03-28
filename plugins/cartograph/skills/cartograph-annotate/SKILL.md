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

The annotate skill orchestrator owns all MCP tool calls. The annotator agent receives
pre-fetched context and returns annotation results as JSON.

### 1. Ensure fresh graph

Call `index_codebase(full=false)` to ensure the graph is up to date.

### 2. Check status

Call `annotation_status()` to see how many nodes are pending, annotated, and failed.
If `pending` is 0, annotation is complete.

### 3. Fetch a batch

Call `get_pending_annotations(batch_size=N)` to receive pending nodes with:
- Source code and file context
- Neighbor information (what calls/imports the node)
- The seed taxonomy of suggested tags

### 4. Format context for the annotator agent

Prepare the batch data as structured context for the annotator agent:
- Include each node's qualified name, source code, file path, and metadata
- Include neighbor context (callers, callees, imports) from the batch
- Include the seed taxonomy reference

### 5. Dispatch annotator agent

Spawn the `cartograph-annotator` agent with the formatted batch data. The agent
analyzes each node and returns a JSON array of annotation results:
```json
[
  {"qualified_name": "...", "summary": "...", "tags": [...], "role": "...", "failed": false},
  ...
]
```

### 6. Submit results

Receive the annotator's JSON array and call `submit_annotations(annotations=[...])` to
write the results back to the graph.

### 7. Repeat

Check if more nodes are pending with `annotation_status()`. If `pending > 0`, loop
back to step 3 and fetch the next batch.

## Parallel processing for large codebases

For codebases with **50+ pending nodes**, use parallel annotator agents:

1. Check total pending count with `annotation_status`
2. Fetch multiple non-overlapping batches via `get_pending_annotations`
3. Format each batch as context and dispatch 2-3 `cartograph-annotator` agents in parallel
4. Collect JSON results from each agent
5. Call `submit_annotations` for each agent's results
6. The orchestrator always owns the MCP calls — agents never call MCP tools directly

See the `cartograph-annotator` agent definition for the agent's input/output contract.

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
