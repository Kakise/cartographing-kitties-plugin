---
name: kitty-brainstorm
description: Turn a rough feature idea into scoped requirements with graph-aware research agents.
compatibility: opencode
---

# Cartographing Kittens: Brainstorm

Use this skill when the user is still clarifying what to build.

## Workflow

1. Call `index_codebase(full=false)`.
2. If the prompt is vague, ask one blocking clarification question at a time when the platform supports it.
3. Build research context with:
   - `annotation_status()`
   - `search()` with 2-4 feature keywords
   - `get_file_structure()` or `get_context_summary()` on top files
   - `query_node()` / `batch_query_nodes()` for key symbols
   - `find_dependencies()` and `find_dependents()` for relevant symbols
4. Dispatch these agents in parallel when helpful:
   - `librarian-kitten-researcher`
   - `librarian-kitten-pattern`
5. Ask only the questions that materially affect scope or architecture.
6. Write the requirements document to `docs/brainstorms/YYYY-MM-DD-NNN-<topic>-requirements.md`.

## Deliverable

The requirements document should cover:
- problem frame
- codebase context
- scope and non-goals
- success criteria
- open questions, if any remain
