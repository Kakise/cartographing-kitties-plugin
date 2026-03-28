---
name: cartograph:lfg
description: Full autonomous engineering workflow — plan, work, review with Cartograph-first agent swarms
argument-hint: "[feature description]"
disable-model-invocation: true
---

Cartograph LFG — autonomous pipeline. Run all steps in order. Do not stop between steps.

## Sequential Phase

1. `/cartograph:plan $ARGUMENTS` — Record the plan file path for steps 3 and 5.
2. `/cartograph:work` — Execute the plan. Use swarm mode: create task list and dispatch parallel worker agents.

## Parallel Phase

After work completes, launch steps 3 and 4 as **parallel background agents**:

3. `/cartograph:review mode:report-only plan:<plan-path-from-step-1>` — Review in report-only mode
4. Run full test suite: `uv run pytest` (or project's test command)

Wait for both to complete.

## Autofix Phase

5. `/cartograph:review mode:autofix plan:<plan-path-from-step-1>` — Apply safe fixes from review findings

## Finalize

6. Commit, push, and create PR with summary of all work done
7. Output `<promise>DONE</promise>` when PR is created
