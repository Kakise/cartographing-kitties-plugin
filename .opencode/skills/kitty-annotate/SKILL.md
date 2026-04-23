---
name: kitty-annotate
description: Generate summaries, tags, and roles for pending graph nodes so semantic search becomes useful.
compatibility: opencode
---

# Cartographing Kittens: Annotate

Use this skill when annotation coverage is low or semantic search results are weak.

## Workflow

1. Call `index_codebase(full=false)`.
2. Call `annotation_status()`.
3. If `pending == 0`, report completion and stop.
4. Fetch a batch with `get_pending_annotations(batch_size=N)`.
5. Format the batch context and dispatch `cartographing-kitten`.
6. Receive annotation JSON and submit it with `submit_annotations(annotations=[...])`.
7. Repeat until pending work is exhausted.

## Large codebases

When there are 50 or more pending nodes, split work into 2-3 non-overlapping batches and run multiple `cartographing-kitten` subagents in parallel.

## Quality bar

- summaries should be specific
- tags should be sparse and meaningful
- unclear nodes should be marked failed instead of guessed
