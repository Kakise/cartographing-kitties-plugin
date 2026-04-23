---
name: kitty:lfg
description: Full autonomous engineering workflow — plan, work, review with Cartographing Kittens-first inline-first orchestration
argument-hint: "[feature description]"
disable-model-invocation: true
---

Cartographing Kittens LFG — autonomous pipeline. Run all steps in order. Default to inline
execution and only use delegation where the runtime supports it cleanly.

## Sequential Phase

1. `/kitty:plan $ARGUMENTS` — Record the plan file path for steps 3 and 5.
2. `/kitty:work` — Execute the plan using the inline-first workflow contract.

## Parallel Phase

After work completes, run steps 3 and 4 in the best supported way for the active runtime.
Parallel execution is optional, not required:

3. `/kitty:review mode:report-only plan:<plan-path-from-step-1>` — Review in report-only mode
4. Run full test suite: `uv run pytest` (or project's test command)

Wait for both to complete.

## Autofix Phase

5. `/kitty:review mode:autofix plan:<plan-path-from-step-1>` — Apply safe fixes from review findings

## Finalize

6. Commit, push, and create PR only when explicitly requested or when the surrounding workflow requires it
7. Output `<promise>DONE</promise>` when the requested autonomous workflow is complete

## Contract

- Must remain meaningful without swarm primitives.
- Must not assume background agents, automatic PR creation, or persistent task teams.
