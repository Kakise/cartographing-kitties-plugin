---
name: kitty-work
description: Execute implementation plans with graph-aware workers that understand dependencies before editing code.
compatibility: opencode
---

# Cartographing Kittens: Work

Use this skill to execute a plan document.

## Workflow

1. Read the plan completely.
2. Call `index_codebase(full=false)`.
3. Break the plan into implementation units and dependency order.
4. Choose execution style:
   - inline for 1-2 small tasks
   - serial subagents for dependent tasks
   - parallel subagents for independent tasks
5. Before handing work to a worker, pre-compute context with:
   - `get_file_structure()` for target files
   - `query_node()` or `batch_query_nodes()` for key symbols
   - `find_dependents()` for blast radius
   - `find_dependencies()` for upstream constraints
   - `rank_nodes()` for importance
   - `annotation_status()` for confidence caveats
6. Workers implement, test, and validate changes.
7. After each unit, re-index and use `graph_diff(file_paths=[...])` or `validate_graph(scope=...)` if the change is structurally sensitive.

## Quality bar

- follow existing patterns from the plan
- write or update tests with the code change
- prefer parallel execution only for truly independent units
