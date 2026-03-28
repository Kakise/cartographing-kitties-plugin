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

1. **Ensure index is fresh** — call `index_codebase(full=false)` if this is the start
   of a conversation or you suspect the index is stale.

2. **Start broad or narrow:**
   - Know the file? → `get_file_structure(file_path="path/to/file.py")`
   - Know a name? → `query_node(name="ClassName")` or `query_node(name="module::func")`
   - Searching by concept? → `search(query="authentication")` (works best after annotation)

3. **Follow relationships** — use the `neighbors` in query results to traverse:
   - Outgoing edges show what the node imports, calls, or inherits
   - Incoming edges show what depends on it

4. **Build understanding iteratively** — start with one entry point and expand outward
   through the graph rather than trying to read everything at once.

## Tools

| Tool | Use for |
|---|---|
| `index_codebase` | Ensure the graph is up to date |
| `get_file_structure` | See all definitions in a file |
| `query_node` | Look up a specific symbol with neighbors |
| `search` | Find nodes by name or summary (best after annotation) |

## Conventions

- **Qualified names** use `::` separator: `module.path::ClassName::method_name`
- **Node kinds**: `module`, `class`, `function`, `method`, `variable`
- **Edge kinds**: `imports`, `calls`, `inherits`, `contains`, `depends_on`

## Tips

- Combine `get_file_structure` → `query_node` for a file-then-dive pattern
- For semantic queries ("find auth code"), check `annotation_status` first — if many
  nodes are pending, run `kitty:annotate` before searching
- See `references/tool-reference.md` for full parameter details
