---
name: kitty-plan
description: Build an implementation plan with graph-aware research, dependency context, and focused subagents.
compatibility: opencode
---

# Cartographing Kittens: Plan

Use this skill after requirements are clear enough to answer how the work should be built.

## Workflow

1. Check `docs/plans/` and `docs/brainstorms/` for an existing matching artifact.
2. Call `index_codebase(full=false)`.
3. Build plan context with:
   - `annotation_status()`
   - `search()` for target-area symbols
   - `get_context_summary()` on top files
   - `batch_query_nodes()` for important symbols
   - `rank_nodes(scope=target_files, limit=10)`
   - `find_dependencies()` and `find_dependents()` on likely change points
4. Dispatch these agents in parallel when useful:
   - `librarian-kitten-researcher`
   - `librarian-kitten-pattern`
   - `librarian-kitten-flow`
   - `librarian-kitten-impact`
5. Ask a clarifying question only when the answer changes architecture, risk, or scope.
6. Write the plan to `docs/plans/YYYY-MM-DD-NNN-<topic>-plan.md`.

## Deliverable

The plan should include:
- implementation units in dependency order
- files and symbols likely to change
- conventions/patterns to follow
- test scenarios
- rollout or risk notes when needed
