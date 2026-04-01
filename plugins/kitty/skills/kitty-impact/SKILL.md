---
name: kitty:impact
description: >
  Impact analysis and refactoring planning with Cartographing Kittens' dependency graph.
  Use when the user asks "what depends on X", "what breaks if I change Y",
  "blast radius", "impact analysis", "who imports this", "who calls this",
  "what does X depend on", "dependency tree", or is planning a refactor,
  rename, or deletion. Use find_dependents for blast radius and find_dependencies
  for understanding what a symbol needs.
---

# Cartographing Kittens: Impact Analysis

Assess the blast radius of changes and understand dependency chains using
Cartographing Kittens' transitive graph traversal.

## When to use

- "What depends on X?" / "What breaks if I change X?"
- "What does X depend on?" / "What does X need?"
- Planning a rename, refactor, or deletion
- Understanding blast radius before modifying shared code
- Tracing call chains or import graphs

## Workflow

The orchestrator pre-computes the full impact context, then dispatches the
`librarian-kitten-impact` agent with the assembled subgraph context. Agents CANNOT
call MCP tools — the orchestrator gathers all data.

### Step 1: Index & Check Coverage

1. Call `index_codebase(full=false)` to ensure the graph is fresh
2. Call `annotation_status()` — check coverage percentage
   - If coverage <30%, warn: "Annotation coverage is low (X%). Impact analysis may miss semantic relationships. Consider running `kitty:annotate` first."

### Step 2: Build Impact Context

1. **Identify the target** — Call `query_node(name="TargetSymbol")` to confirm the right
   node and capture its metadata, neighbors, and edge kinds.

2. **Assess blast radius** — Call `find_dependents(name="TargetSymbol", max_depth=4)` for
   the transitive blast radius. Pay attention to:
   - `depth: 1` = direct dependents (most affected)
   - Higher depth = transitive (may need testing but less likely to break)

3. **Understand upstream constraints** — Call `find_dependencies(name="TargetSymbol", max_depth=3)`
   to see what the target relies on.

4. **Rank by importance** — Call `rank_nodes(scope=dependent_files)` to weight which
   dependents are most structurally important (highest-ranked dependents deserve the
   most attention).

5. **Structural health check** — Call `validate_graph(scope=target_files)` to detect
   any existing structural issues (cycles, orphans, missing edges) in the affected area.

6. **Filter by relationship type** — use `edge_kinds` to focus:
   - `["calls"]` — who calls this function?
   - `["imports"]` — who imports this module?
   - `["inherits"]` — what subclasses this class?

### Step 3: Format Subgraph Context

Assemble the collected data into a structured text block:

```
## Subgraph Context

### Annotation Status
- Total nodes: N, Annotated: M (X%)

### Target Symbol
- `qualified::name` — kind, role, tags, summary
- Neighbors: [callers, callees, imports, inherits]

### Blast Radius (find_dependents, max_depth=4)
| Qualified Name | Depth | Kind | Summary | Role | Importance |
|---|---|---|---|---|---|
| consumer::symbol | 1 | function | "..." | handler | 0.85 |

### Upstream Dependencies (find_dependencies, max_depth=3)
| Qualified Name | Kind | Summary | Role |
|---|---|---|---|
| dep::symbol | class | "..." | model |

### Importance Ranking (rank_nodes)
| Qualified Name | Score | Kind | Role |
|---|---|---|---|
| critical::symbol | 0.95 | class | core |

### Structural Health (validate_graph)
- Issues: [list any cycles, orphans, or missing edges]
```

### Step 4: Dispatch Agent

Dispatch **`librarian-kitten-impact`** with the full subgraph context, the target
symbol name, and the user's question/intent.

### Step 5: Present Results

Relay the agent's findings to the user, including:
- Impact summary with severity assessment
- List of affected files and symbols ranked by importance
- Recommended actions (test updates, contract checks, etc.)

### Interpreting results

- **High dependent count at depth 1** → change will have wide direct impact, proceed carefully
- **Deep dependency chains** → consider whether transitive dependents will actually break
- **Cross-file dependents** → identify test files that need updating
- **No dependents** → safe to change freely
- **High-importance dependents** → extra care needed, verify contracts

## Tools

| Tool | Use for |
|---|---|
| `index_codebase` | Ensure the graph is up to date |
| `annotation_status` | Check annotation coverage |
| `query_node` | Understand a symbol before analyzing it |
| `find_dependents` | What depends on X (blast radius) |
| `find_dependencies` | What X depends on (upstream constraints) |
| `rank_nodes` | Importance scoring for affected symbols |
| `validate_graph` | Structural health checks (cycles, orphans) |

## Parameters

- `edge_kinds` — filter to `imports`, `calls`, `inherits`, `contains`, or `depends_on`
- `max_depth` — default 5, reduce for focused analysis or increase for deep trees

## Tips

- Always check `find_dependents` before renaming or deleting public symbols
- Use `max_depth=1` for a quick direct-impact check
- Use `rank_nodes` to focus attention on the most important dependents
- `validate_graph` catches pre-existing structural issues that a change might worsen
- See `references/tool-reference.md` for full parameter details
