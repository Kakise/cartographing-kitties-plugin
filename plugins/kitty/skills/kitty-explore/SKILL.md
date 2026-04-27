---
name: kitty:explore
description: >
  Structural codebase exploration using Cartographing Kittens' graph. Use when the user asks
  "what's in this file", "how is this organized", "explore the codebase", "navigate
  the code", "understand the structure", "what does this module contain", or wants
  to browse definitions, imports, and relationships. Prefer over grep/glob for
  structural and relational questions about code organization.
---

# Cartographing Kittens: Explore

Explore codebase structure through the Cartographing Kittens graph — definitions, imports,
call relationships, and inheritance.

## When to use

- "What's in this file / module / package?"
- "How is this project organized?"
- "What does X define / export / contain?"
- "Show me the structure of Y"
- Browsing code organization before making changes

## Workflow

The orchestrator builds all context directly — no agent dispatch needed for exploration.
Agents CANNOT call MCP tools, so the orchestrator IS the explorer.

### Step 1: Ensure Index & Check Coverage

1. Call `index_codebase(full=false)` to ensure the graph is fresh
2. Call `annotation_status()` — check coverage percentage
   - If coverage <30%, warn: "Annotation coverage is low (X%). Semantic search and summaries will be limited. Consider running `kitty:annotate` first."

### Step 2: Gather Context (choose tools based on the question)

**Broad overview (file or module exploration):**
- Call `get_context_summary(file_paths=[...])` for a token-efficient overview of files/modules
- Call `rank_nodes(scope=target_files, limit=10)` to surface the most important symbols

**Multi-symbol deep dive:**
- Call `batch_query_nodes(names=[...], include_neighbors=true)` for detailed info on multiple symbols at once

**Relationship exploration:**
- Call `find_dependents(name=..., max_depth=2)` for "who uses this?"
- Call `find_dependencies(name=..., max_depth=2)` for "what does this depend on?"

**Semantic/concept search:**
- Call `search(query="keyword")` (best after annotation)

**Single symbol lookup:**
- Call `query_node(name="ClassName")` for a single symbol with neighbors

### Step 3: Present Results

Format the gathered context as structured output for the user. Include:
- File/module structure with definitions
- Importance rankings (from `rank_nodes`)
- Key relationships (dependencies, dependents)
- Annotation coverage warning if applicable

## Tools

| Tool | Use for |
|---|---|
| `index_codebase` | Ensure the graph is up to date |
| `annotation_status` | Check annotation coverage, warn if low |
| `get_context_summary` | Token-efficient overview of files/modules |
| `batch_query_nodes` | Look up multiple symbols at once with neighbors |
| `get_file_structure` | See all definitions in a single file |
| `query_node` | Look up a single symbol with neighbors |
| `find_dependents` | Who uses this symbol? (blast radius) |
| `find_dependencies` | What does this symbol depend on? |
| `rank_nodes` | Surface the most important symbols in a scope |
| `search` | Find nodes by name or summary (best after annotation) |

## Conventions

- **Qualified names** use `::` separator: `module.path::ClassName::method_name`
- **Node kinds**: `module`, `class`, `function`, `method`, `variable`
- **Edge kinds**: `imports`, `calls`, `inherits`, `contains`, `depends_on`

## Tips

- Use `get_context_summary` for broad exploration — it is more token-efficient than calling `get_file_structure` + `query_node` for each file
- Use `batch_query_nodes` instead of multiple `query_node` calls when exploring several symbols
- Use `rank_nodes` to identify the most structurally important symbols before diving deeper
- For semantic queries ("find auth code"), check `annotation_status` first — if many
  nodes are pending, run `kitty:annotate` before searching
- See `kitty/references/tool-reference/` for full parameter details
