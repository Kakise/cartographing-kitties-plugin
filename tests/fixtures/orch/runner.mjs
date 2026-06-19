// Behavioral runner for *.orch.js orchestration scripts.
//
// Invoked by tests/test_orchestration_scripts.py as:
//   node runner.mjs <script-abs-path> <mode> <bundle-abs-path>
//
// It defines stub workflow globals (agent/parallel/pipeline/phase/log/args/budget),
// wraps the orchestration-script body in an async function (the Workflow runtime
// does the same — the scripts use top-level `await` and a top-level `return`, which
// are only legal inside a function), runs it, and prints a JSON report on stdout:
//   { ok, error, result, calls, agentCalls, faultedLabel, faultedId }
//
// `mode` controls how the stub `agent()` behaves so the test can exercise both a
// NORMAL run and FAULT runs (throw / null / schema-invalid) for a single item.
//
// Fault injection is SCRIPT-AGNOSTIC: the fault targets the FIRST agent() call of
// the run regardless of label or script, then keeps faulting every later call that
// belongs to the SAME item (same id segment of the `stage:id[:extra]` label). That
// way a bounded-retry script (MAX_ATTEMPTS=2) cannot quietly "recover" the faulted
// item on a re-dispatch — it must journal it as failed, exactly the property under
// test. Every call for any OTHER item behaves normally.

import { readFile } from 'node:fs/promises'

const [scriptPath, mode, bundlePath] = process.argv.slice(2)

// ── stub globals ──────────────────────────────────────────────────────────────
const calls = []

// A schema-valid reviewer return: one P1 finding (so the verify stage fires) plus a P3.
function reviewReturn(dim) {
  return {
    status: 'ok',
    agent: `expert-kitten-${dim}`,
    role: 'review',
    summary: `stub ${dim} review`,
    confidence: 0.9,
    findings_or_observations: [
      {
        severity: 'P1',
        category: dim,
        location: 'src/x.py:10',
        issue: `stub ${dim} P1`,
        guidance: 'fix it',
        confidence: 0.8,
        autofix_class: 'manual',
      },
      {
        severity: 'P3',
        category: dim,
        location: 'src/x.py:20',
        issue: `stub ${dim} P3`,
        guidance: 'nit',
        confidence: 0.5,
        autofix_class: 'advisory',
      },
    ],
  }
}

function verifyReturn() {
  return { status: 'ok', real: true, rationale: 'confirmed', confidence: 0.95 }
}

// Which item the fault is injected against (first item by default).
let faultItem = null

async function agent(prompt, opts = {}) {
  const label = opts.label || ''
  calls.push({ label, phase: opts.phase, model: opts.model, effort: opts.effort, agentType: opts.agentType })
  // Every shipped script labels its agent calls `<stage>:<itemId>[:extra]`, so the item id
  // is the SECOND `:`-segment regardless of which script/stage is running.
  const stage = label.split(':')[0]
  const itemId = label.split(':')[1]

  // FAULT injection (script-agnostic): fault EVERY call belonging to the targeted item,
  // regardless of stage prefix. A bounded-retry script (MAX_ATTEMPTS=2) re-dispatches the
  // same item, which faults again — so it cannot quietly "recover" and MUST journal it as
  // failed. Calls for any OTHER item behave normally.
  if (faultItem && itemId === faultItem) {
    if (mode === 'throw') throw new Error(`stub agent boom for ${itemId}`)
    if (mode === 'null') return null
    if (mode === 'invalid') return { status: 'ok' } // missing findings_or_observations etc.
  }
  if (stage === 'review') return reviewReturn(itemId)
  if (stage === 'verify') return verifyReturn()
  // Generic schema-shaped fallback for any other stage/script.
  return { status: 'ok', findings_or_observations: [], summary: 'stub', reported_model: opts.model || 'stub', evidence: 'stub' }
}

async function parallel(thunks) {
  // Mirror the contract: a thrown thunk resolves to null (failed), never rejects the batch.
  return Promise.all(
    (thunks || []).map((t) => Promise.resolve().then(() => t()).catch(() => null)),
  )
}

async function pipeline(items, ...stages) {
  const out = []
  for (const item of items || []) {
    let acc = item
    for (const stage of stages) {
      acc = await Promise.resolve().then(() => stage(acc)).catch(() => null)
    }
    out.push(acc)
  }
  return out
}

function phase(_title) {}
function log(_msg) {}
const budget = { tokens: 1_000_000, agents: 1000 }

// ── args the orchestrator would pass for a review run ──────────────────────────
const args = {
  bundlePath,
  items: [
    { id: 'correctness', active: true },
    { id: 'testing', active: true },
  ],
  tiers: {
    correctness: { model: 'sonnet', effort: 'medium' },
    testing: { model: 'sonnet', effort: 'medium' },
    verify: { model: 'opus', effort: 'xhigh' },
  },
  lensRefs: {
    correctness: 'Look for logic errors, edge cases, and broken state transitions.',
    testing: 'Look for missing or weak test coverage.',
  },
  dispatch: 'workflow',
}
faultItem = mode === 'normal' ? null : args.items[0].id

// ── wrap + run the script body (top-level await/return ⇒ must be inside a fn) ──
// `export const meta = …` is an ES-module statement illegal inside a Function body, so
// strip the leading `export ` (the Workflow runtime hoists meta out before executing the
// body the same way). The `meta` literal itself stays a valid `const` declaration.
const raw = await readFile(scriptPath, 'utf8')
const src = raw.replace(/^\s*export\s+const\s+meta\b/m, 'const meta')
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const fn = new AsyncFunction(
  'agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget',
  src,
)

const report = { ok: false, error: null, result: null, calls: [], agentCalls: 0 }
try {
  const result = await fn(agent, parallel, pipeline, phase, log, args, budget)
  report.ok = true
  report.result = result ?? null
} catch (e) {
  report.ok = false
  report.error = String(e && e.stack ? e.stack : e)
}
report.calls = calls
report.agentCalls = calls.length
process.stdout.write(JSON.stringify(report))
