---
description: Index or refresh the Cartographing Kittens graph
---

Use the Cartographing Kittens MCP server to update the code graph.

If `$ARGUMENTS` contains `full` or `re-index`, call `index_codebase(full=true)`. Otherwise use `index_codebase(full=false)`.

Report parsed files, nodes created, edges created, and whether the run was incremental or full.
