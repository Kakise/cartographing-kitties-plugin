---
description: Index or re-index the codebase graph
allowed-tools: mcp__plugin_kitty_kitty__index_codebase
---

Call `index_codebase` to update the code graph.

If the user says "full" or "re-index", pass `full=true`. Otherwise use `full=false` for incremental indexing.

Report the stats: files parsed, nodes created, edges created.
