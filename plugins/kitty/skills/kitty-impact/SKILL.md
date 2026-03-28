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

### Before a change

1. **Identify the target** — `query_node(name="TargetSymbol")` to confirm you have
   the right node and see its immediate connections.

2. **Assess blast radius** — `find_dependents(name="TargetSymbol")` shows everything
   that depends on this node, transitively. Pay attention to:
   - `depth: 1` = direct dependents (most affected)
   - Higher depth = transitive (may need testing but less likely to break)

3. **Understand dependencies** — `find_dependencies(name="TargetSymbol")` shows what
   the target needs. Useful for understanding if a refactor will break its own imports.

4. **Filter by relationship type** — use `edge_kinds` to focus:
   - `["calls"]` — who calls this function?
   - `["imports"]` — who imports this module?
   - `["inherits"]` — what subclasses this class?

### Interpreting results

- **High dependent count at depth 1** → change will have wide direct impact, proceed carefully
- **Deep dependency chains** → consider whether transitive dependents will actually break
- **Cross-file dependents** → identify test files that need updating
- **No dependents** → safe to change freely

## Tools

| Tool | Use for |
|---|---|
| `query_node` | Understand a symbol before analyzing it |
| `find_dependents` | What depends on X (blast radius) |
| `find_dependencies` | What X depends on (requirements) |

## Parameters

- `edge_kinds` — filter to `imports`, `calls`, `inherits`, `contains`, or `depends_on`
- `max_depth` — default 5, reduce for focused analysis or increase for deep trees

## Tips

- Always check `find_dependents` before renaming or deleting public symbols
- Use `max_depth=1` for a quick direct-impact check
- Combine with `get_file_structure` to identify affected test files
- See `references/tool-reference.md` for full parameter details
