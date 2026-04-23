---
name: kitty-explore
description: Explore file structure, key symbols, and relationships using the Cartographing Kittens graph.
compatibility: opencode
---

# Cartographing Kittens: Explore

Use this skill when the user asks how code is organized, what a file contains, or how a symbol fits into the rest of the codebase.

## Workflow

1. Call `index_codebase(full=false)`.
2. Call `annotation_status()` and warn if coverage is low.
3. Choose the smallest useful context set:
   - `get_context_summary(file_paths=[...])` for broad overview
   - `get_file_structure(file_path=...)` for one file
   - `batch_query_nodes(names=[...], include_neighbors=true)` for several important symbols
   - `query_node(name=...)` for one symbol
   - `find_dependencies` / `find_dependents` for relationship questions
   - `rank_nodes(scope=..., limit=10)` to highlight important symbols
4. Present a structured overview with file/module layout, important symbols, and key relationships.

## Output expectations

Include:
- target files or modules
- key classes/functions
- important inbound and outbound relationships
- coverage caveat when annotation coverage is weak

Use grep/glob only for non-structural text lookups.
