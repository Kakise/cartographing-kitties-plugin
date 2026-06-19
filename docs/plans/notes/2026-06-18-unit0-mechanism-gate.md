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

---

## Unit 5 — `review.orch.js` live smoke test (Step 5)

**Date:** 2026-06-19
**Verdict:** ✅ `review.orch.js` runs end-to-end under the real Workflow runtime.

Two live runs of the shipped `review.orch.js`, dispatched **inline via the Workflow tool's
`script` input** (the real conductor path — never `scriptPath`/`name`) against the
`tests/fixtures/orch/bundle.md` fixture, items `[correctness, testing]`, tiers
`sonnet` (review) / `opus` (verify).

### Run 1 — `wf_0938e8bc-09a` (6 agents, ~132k tok, 119s)

- **Caught a real runtime-blocking defect the node-stub harness could not.** The first
  dispatch was REJECTED: `meta must be a pure literal: non-literal node type in meta:
  BinaryExpression`. All six `*.orch.js` built `meta.description` with `'…' + '…'` string
  concatenation — valid plain JS (so the node runner never noticed), but the live runtime
  refuses it. Fix: collapsed every script's `meta.description` to a single string literal,
  and added a static `test_meta_is_pure_literal` harness check so the whole class regresses
  in CI rather than only at dispatch.
- After the fix: `ledger=[{correctness,done,1},{testing,done,1}]`, `failed=[]`. The
  reviewers also flagged that the fixture bundle referenced a non-existent
  `cartograph.parsing.python::PythonParser::extract` and a wrong line range for
  `discover_files` — both verified against the tree and corrected (the bundle now points at
  `ParserRegistry::parse_file`, `extract_definitions`, `discover_files` with real
  paths/ranges).

### Run 2 — `wf_41ac7f3d-fa6` (3 agents, ~64k tok, 86s), corrected bundle

- `ledger=[{correctness,done,1},{testing,done,1}]`, `failed=[]`; clean end-to-end.
- No more dangling-reference findings — the corrected fixture resolves to real symbols.
- Remaining findings were genuine observations about the *real* parsing/indexing code the
  bundle now points at (`extract_definitions` silent `[]` for unknown languages;
  `_is_gitignored` full-path `fnmatch` dead branch; missing `parse_file` error tests).
  Pre-existing, out of scope for the orchestration rewrite; a `.gitignore`-coverage
  follow-up was filed.

**Conclusion:** Step 5 satisfied. `review.orch.js` runs end-to-end under the real runtime;
schema enforcement, the per-item ledger, and the `failed` envelope behave as designed. The
node-stub harness (`tests/test_orchestration_scripts.py`, 58 tests) exercises all six
scripts statically + behaviorally; the live run validated the one property the stub
structurally cannot (the runtime's pure-literal `meta` contract).
