# Unit 0 — Mechanism gate verdict (model routing)

**Date:** 2026-06-18
**Run:** `wf_f6d8256e-43e` (3 agents, 8.5s)
**Verdict:** `model_routing = real` ✅

## What was tested

The `_probe.orch.js` workflow spawned three agents via `agent(prompt, {model})` at
`haiku`, `sonnet`, and `opus`, each asked to report its own underlying model id. The
session (main-loop) model is Opus 4.8. If the Workflow `agent()` resolver were subject to
#43869 ("everything resolves to the parent model"), all three would report Opus.

## Results (verbatim)

| requested | reported_model | evidence |
|-----------|----------------|----------|
| `haiku`  | `claude-haiku-4-5-20251001` | system-reminder: "powered by the model named Haiku 4.5 … claude-haiku-4-5-20251001" |
| `sonnet` | `claude-sonnet-4-6` | system prompt: "powered by the model named Sonnet 4.6 … claude-sonnet-4-6" |
| `opus`   | `claude-opus-4-8[1m]` | system prompt: "powered by the model named Opus 4.8 (1M context) … claude-opus-4-8[1m]" |

Each agent ran on the **requested** model, distinct from the others and from the session
model where applicable. The Workflow `agent({model})` resolver routes correctly.

## Consequence

- **No spec pivot.** §4 complexity-tiering (`trivial→haiku`, `standard→sonnet`,
  `hard→opus`) takes real effect on the workflow path. Goal 3 (smart dispatch) stands.
- Units 5–8 keep `model` (and `effort`) in their `args.tiers` dispatch.
- The fallback path still cannot route models (F1/#43869 on the Task path is unaffected and
  remains broken) — the §1 honest-limitation about fallback model uniformity is unchanged.

## Caveat

Self-report relies on each agent's injected system prompt declaring its model id. This is
the documented, best-available signal and is internally consistent (three distinct,
tier-matching ids). Treated as sufficient evidence to proceed.
