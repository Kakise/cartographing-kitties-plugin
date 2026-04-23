---
name: kitty-review
description: Review code changes with diff context plus graph-aware structural analysis, optionally applying safe fixes.
compatibility: opencode
---

# Cartographing Kittens: Review

Use this skill for code review, pre-PR review, or report-only structural verification.

## Modes

- default: interactive review
- `mode:report-only`: no edits
- `mode:autofix`: apply only safe fixes

## Workflow

1. Compute the diff against the chosen base.
2. Build an intent summary from the branch, commits, PR details, or linked plan.
3. Call `annotation_status()` and warn if more than half the graph is unannotated.
4. For changed files and symbols, gather:
   - `get_file_structure()`
   - `query_node()` or `batch_query_nodes()`
   - `find_dependents()` for public changed symbols
   - `find_dependencies()` for upstream context
5. Dispatch reviewer subagents in parallel:
   - `expert-kitten-correctness`
   - `expert-kitten-testing`
   - `expert-kitten-impact` when blast radius is broad
   - `expert-kitten-structure` when new files or architectural shifts appear
6. Merge findings by severity and remove duplicates.
7. In autofix mode, apply only safe fixes and report everything else.

## Output

Present findings in severity order with file locations, guidance, and residual risks.
