---
description: Show index status, annotation coverage, and memory stats
allowed-tools: mcp__plugin_kitty_kitty__annotation_status, mcp__plugin_kitty_kitty__query_litter_box, mcp__plugin_kitty_kitty__query_treat_box
---

Call `annotation_status` to get the current index and annotation state. Then call `query_litter_box` and `query_treat_box` with no filters to get entry counts.

Present a summary dashboard showing:
- Files indexed and node count
- Annotation coverage percentage
- Litter-box entries (by category)
- Treat-box entries (by category)
