# Annotation Workflow

After indexing, nodes in the graph are "bare" — they have names, kinds, and locations
but no summaries, tags, or roles. Annotation enriches the graph so semantic search
works well. The agent (you) generates annotations by reading source code context.

## Why annotate?

Without annotation, `search` only matches node names. With annotation, it matches
against human-readable summaries and tags, so queries like "find authentication code"
or "what handles payments" work well.

## The workflow

### 1. Check status

```
annotation_status()
```

If `pending` is 0, you're done. If `pending` > 0, proceed.

### 2. Get a batch

```
get_pending_annotations(batch_size=10)
```

This returns nodes with their source code, file context, and neighbor information.
You also get a seed taxonomy of suggested tags.

### 3. Generate annotations

For each node in the batch, read the source code and context, then generate:

- **summary** (str): One sentence describing what the node does. Be specific —
  "Validates user input against schema" is better than "Handles validation".

- **tags** (list[str]): Categorical tags. Use the seed taxonomy when it fits, but
  don't force it. Good tags describe the domain ("authentication", "database"),
  the layer ("middleware", "service"), or the pattern ("singleton", "factory").

- **role** (str): A short role description. Think of it as the node's job title:
  "Request handler", "Data access layer", "Input validator", "Configuration manager".

If you can't understand a node (e.g. the source is too complex or ambiguous), set
`failed: true` instead of guessing.

### 4. Submit

```
submit_annotations(annotations=[
  {
    "qualified_name": "mod.func",
    "summary": "Validates input",
    "tags": ["validation"],
    "role": "Input validator"
  },
  ...
])
```

### 5. Repeat

Keep getting batches until `annotation_status` shows `pending: 0`.

## Performance tips

- **Batch size**: Use `batch_size=10` for most cases. You can go up to 20 for simple
  codebases (functions with clear names) or down to 5 for complex ones.

- **Parallel annotation**: For codebases with 50+ pending nodes, spawn 2-3 subagents
  to process batches concurrently. Each subagent gets its own batch and submits independently.

- **Skip trivial nodes**: If a node is a simple getter/setter or constant, a terse
  summary is fine. Save your attention for complex logic.

- **Use neighbor context**: The batch includes neighbor information for a reason —
  understanding what calls a function helps you summarize it accurately.

## Seed taxonomy

The server provides a default set of tags. Use these when they fit:

`authentication`, `database`, `api`, `validation`, `configuration`, `middleware`,
`service`, `model`, `controller`, `utility`, `testing`, `error-handling`,
`caching`, `logging`, `serialization`, `formatting`, `parsing`, `io`

Don't limit yourself to these — if the code is about "payment processing" or
"websocket management", create that tag. The taxonomy grows organically.

## Consuming annotations

Annotations are not just for search — they are consumed by all Cartograph agents
through the orchestrator-mediated architecture.

### How it works

1. **Annotator writes** — The annotate skill orchestrator dispatches the annotator
   agent with pre-fetched pending nodes. The agent returns annotation JSON, and the
   orchestrator calls `submit_annotations` to write results to the graph.

2. **Graph stores** — Summaries go to the `summary` column (indexed by FTS5 for search).
   Tags and roles go to the `properties` JSON column.

3. **Tools surface** — All node-returning MCP tools (`query_node`, `search`,
   `get_file_structure`, `find_dependencies`, `find_dependents`) include `tags`,
   `role`, `summary`, and `annotation_status` in every node response.

4. **Orchestrators query** — Skill orchestrators (review, plan, work, brainstorm)
   call MCP tools to build annotated subgraph context before dispatching agents.

5. **Agents consume** — Agents receive pre-computed graph context as structured text,
   including summaries, roles, and tags for all relevant nodes. They use this to:
   - Understand node purpose without reading full source files
   - Classify code by domain layer using roles
   - Group blast radius by role/tag for semantic impact assessment
   - Check contracts across relationships between changed nodes

### The subgraph context format

Orchestrators format graph data into a standard text structure with sections for:
- Annotation Status (coverage counts)
- Changed/Target Nodes (with summaries, roles, tags)
- Edges Between Changed Nodes (contracts to verify)
- Neighbors (1-hop callers/callees with annotations)
- Transitive Dependents (blast radius with depth and roles)
- Transitive Dependencies (upstream context)

See `subgraph-context-format.md` for the full specification.
