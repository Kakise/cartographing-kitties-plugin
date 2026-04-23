---
name: kitty-lfg
description: Run the full graph-aware engineering workflow from planning through review.
compatibility: opencode
---

# Cartographing Kittens: LFG

Use this skill for the full pipeline when the user wants end-to-end execution.

## Pipeline

1. Run `kitty-plan` and capture the resulting plan path.
2. Run `kitty-work` against that plan.
3. Run the relevant test suite.
4. Run `kitty-review mode:report-only plan:<plan-path>`.
5. If safe follow-up fixes are warranted and requested by mode or user intent, run `kitty-review mode:autofix plan:<plan-path>`.
6. Summarize what changed, how it was verified, and any remaining risks.

Do not skip testing or review just because implementation succeeded.
