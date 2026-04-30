---
description: Show status of every plan under docs/plans/
allowed-tools: Bash
---

Run `uv run python scripts/plan_status.py report` and present the resulting table to the user.

For each plan, surface:
- File name and plan title
- Plan-level status (draft, active, in_progress, complete, superseded, abandoned)
- Unit progress (e.g., 3/7 complete)
- implemented_in / superseded_by / abandoned_reason when set
- Whether the current branch matches the plan slug

If the user passes additional flags through `$ARGUMENTS` (for example `--format json` or
`audit --strict`), forward them verbatim to `scripts/plan_status.py`.
