---
name: kitty-impact
description: Assess blast radius, upstream constraints, and refactor safety with Cartographing Kittens dependency analysis.
compatibility: opencode
---

# Cartographing Kittens: Impact

Use this skill for "what depends on X", "what does X depend on", rename/delete planning, and change-risk analysis.

## Workflow

1. Call `index_codebase(full=false)`.
2. Call `annotation_status()` and warn if coverage is below 30%.
3. Resolve the target with `query_node(name=...)`.
4. Gather blast radius with `find_dependents(name=..., max_depth=3 or 4)`.
5. Gather upstream constraints with `find_dependencies(name=..., max_depth=2 or 3)`.
6. Rank affected symbols with `rank_nodes(scope=affected_files, limit=10)`.
7. Run `validate_graph(scope=affected_files)` if the request is about a refactor or risky change.
8. If needed, dispatch `librarian-kitten-impact` with the assembled context.

## Report

Return:
- direct dependents first
- important transitive dependents
- critical upstream dependencies
- test/update recommendations
- whether the change looks low, medium, or high risk
