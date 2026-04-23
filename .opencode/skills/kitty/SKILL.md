---
name: kitty
description: Route structural codebase questions and change-planning work to the right Cartographing Kittens workflow in OpenCode.
compatibility: opencode
---

# Cartographing Kittens

Use Cartographing Kittens when the request is about code structure, relationships, blast radius,
semantic code search, or graph-aware planning.

Prefer Cartographing Kittens over plain text search for:
- what depends on a symbol
- what a file or module contains
- how definitions relate
- what might break after a change
- finding code by concept after annotation

## Dispatch guide

- Use `kitty-explore` for structural exploration and architecture questions.
- Use `kitty-impact` for dependency analysis, blast radius, and refactor safety.
- Use `kitty-annotate` to enrich graph nodes for semantic search.
- Use `kitty-brainstorm` to turn a rough idea into scoped requirements.
- Use `kitty-plan` to produce an implementation plan.
- Use `kitty-work` to execute a plan with graph-aware workers.
- Use `kitty-review` to run graph-aware code review.
- Use `kitty-lfg` for the full plan -> work -> review pipeline.

## Quick rules

1. Run `index_codebase(full=false)` when graph freshness is uncertain.
2. Check `annotation_status()` before relying on semantic search.
3. Use `get_context_summary`, `batch_query_nodes`, and `rank_nodes` before falling back to repeated file reads.
4. Use grep/glob only for literal text lookups, not structural questions.

## Core tools

- `index_codebase`
- `annotation_status`
- `search`
- `query_node`
- `batch_query_nodes`
- `get_file_structure`
- `get_context_summary`
- `find_dependencies`
- `find_dependents`
- `rank_nodes`
- `validate_graph`
- `graph_diff`

Qualified names use `::`, and the graph is stored under `.pawprints/graph.db`.
