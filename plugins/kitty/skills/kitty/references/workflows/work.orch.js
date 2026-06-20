// RUN-BOUNDARY NOTE (spec §3.1 / §9): the per-unit re-index + graph_diff +
// validate_graph (and plan-state mutation + commit) are MCP-gated MAIN-LOOP steps.
// They are INTENTIONALLY NOT in this script — this run performs exactly one MCP-free
// fan-out (this unit's intra-unit work), returns, and the orchestrator does the
// re-index/validate/commit at the run boundary before invoking the next unit's run.
export const meta = {
  name: 'kitty-work',
  description: 'kitty:work fan-out for ONE implementation unit: parallel sub-task implementers produce the unit changes, then a two-gate self-review (spec-compliance and code-quality) verifies the unit before it returns. Re-index/validate/commit are a main-loop boundary.',
  phases: [{ title: 'Implement' }, { title: 'SelfReview' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})

// ── shared schemas (mirror references/agent-output-contract.md) ──
const FINDING = {
  type: 'object',
  required: ['severity', 'category', 'location', 'issue', 'guidance', 'confidence', 'autofix_class'],
  additionalProperties: true,
  properties: {
    severity: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3'] },
    category: { type: 'string' },
    location: { type: 'string' },
    issue: { type: 'string' },
    guidance: { type: 'string' },
    confidence: { type: 'number' },
    autofix_class: { type: 'string', enum: ['safe_auto', 'gated_auto', 'manual', 'advisory'] },
  },
}
// findings_or_observations entries: { file, change_summary, lines_touched }.
const IMPLEMENT_SCHEMA = {
  type: 'object',
  required: ['status', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array' },
  },
}
const GATE_SCHEMA = {
  type: 'object',
  required: ['status', 'verdict', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    verdict: { type: 'string', enum: ['pass', 'fail'] },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array', items: FINDING },
  },
}

// ── per-item ledger + retry helper (spec §6) ──
const MAX_ATTEMPTS = 2
const makeLedger = (its) => its.map((it) => ({ id: it.id, status: 'pending', attempts: 0 }))
const entryFor = (ledger, id) => ledger.find((e) => e.id === id)
// A return fails if it is null/empty, throws, or has a non-ok status. `requiredKey`
// demands a shape field so a schema-invalid/empty return counts as failed, not silently
// accepted (§6).
function isOkReturn(r, requiredKey) {
  if (!r || typeof r !== 'object' || Object.keys(r).length === 0) return false
  if (r.status && r.status !== 'ok') return false
  return !(requiredKey && r[requiredKey] === undefined)
}

// ── agentType mapping ──
const IMPL_AGENT = 'kitty:librarian-kitten'
const GATE_AGENT = {
  'spec-compliance': 'kitty:expert-kitten-correctness',
  'code-quality': 'kitty:expert-kitten-structure',
}

const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const HARD_GATE = tiers.gate ?? { model: 'opus', effort: 'high' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY your one bundle section. Do not call MCP. '

// The unit's sub-tasks to implement in parallel (each is one item with an id).
const items = (A.items ?? []).filter((it) => it && it.id)
const ledger = makeLedger(items)

// ── Stage 1: one sub-task implementer ──
async function implement(item) {
  const id = item.id
  const tier = tiers[id] ?? STANDARD
  const lens = lensRefs[id] ?? lensRefs.implement ?? ''
  const r = await agent(
    `${PROLOGUE}You implement sub-task "${id}" of this unit. ${lens}\n`
      + 'Apply the Memory lessons section. Produce well-factored changes that stay under '
      + 'the produced-code soft cap (300 lines/file); surface any unavoidable seam instead '
      + 'of silently exceeding it. Return an envelope per references/agent-output-contract.md '
      + '(status + findings_or_observations[] of { file, change_summary, lines_touched }).',
    { label: `implement:${id}`, phase: 'Implement', schema: IMPLEMENT_SCHEMA, agentType: IMPL_AGENT, ...tier },
  )
  return { id, result: r }
}

// ── dispatch one sub-task, recording the ledger ──
async function runItem(item) {
  const entry = entryFor(ledger, item.id)
  entry.attempts += 1
  let r
  try {
    r = (await implement(item)).result
  } catch (_e) {
    r = null
  }
  if (!isOkReturn(r, 'findings_or_observations')) {
    entry.status = (r && r.status === 'needs_more_context') ? 'needs_context' : 'failed'
    return { id: item.id, changes: [] }
  }
  entry.status = 'done'
  const changes = Array.isArray(r.findings_or_observations) ? r.findings_or_observations : []
  return { id: item.id, changes, summary: r.summary }
}

// ── bounded re-dispatch of non-done items (spec §6) ──
function pending() {
  return items.filter((it) => {
    const e = entryFor(ledger, it.id)
    return e.status !== 'done' && e.attempts < MAX_ATTEMPTS
  })
}

phase('Implement')
let collected = await parallel(items.map((it) => () => runItem(it).catch(() => null)))
// A thrown/null thunk resolves to null → treat as failed, never dropped.
for (let i = 0; i < items.length; i += 1) {
  if (!collected[i]) {
    const e = entryFor(ledger, items[i].id)
    if (e && e.status !== 'done') e.status = 'failed'
  }
}
let toRetry = pending()
while (toRetry.length > 0) {
  log(`re-dispatching ${toRetry.length} failed/needs_context sub-task(s)`)
  const redone = await parallel(toRetry.map((it) => () => runItem(it).catch(() => null)))
  redone.forEach((r, i) => {
    if (r && Array.isArray(r.changes)) {
      const slot = collected.findIndex((c) => c && c.id === toRetry[i].id)
      if (slot >= 0) collected[slot] = r
      else collected.push(r)
    } else {
      const e = entryFor(ledger, toRetry[i].id)
      if (e && e.status !== 'done') e.status = 'failed'
    }
  })
  toRetry = pending()
}

const changes = []
for (const c of collected) {
  if (c && Array.isArray(c.changes)) {
    for (const ch of c.changes) changes.push({ subtask: c.id, ...ch })
  }
}

// ── Stage 2: two-gate self-review of the assembled unit (spec §9) ──
// Run only if at least one sub-task produced changes; both gates run in parallel.
async function gate(name) {
  const lens = lensRefs[name] ?? ''
  const r = await agent(
    `${PROLOGUE}You are the ${name} self-review gate for this completed unit. ${lens}\n`
      + 'Inspect the produced changes against the unit spec and code-quality standards. '
      + 'Return {"status":"ok","verdict":"pass|fail","findings_or_observations":[...]} per '
      + 'references/agent-output-contract.md; each finding needs severity, category, location, '
      + 'issue, guidance, confidence, autofix_class.',
    { label: `gate:${name}`, phase: 'SelfReview', schema: GATE_SCHEMA, agentType: GATE_AGENT[name], ...HARD_GATE },
  ).then((v) => ({ name, v })).catch(() => ({ name, v: null }))
  return r
}

let gates = {}
if (changes.length > 0) {
  phase('SelfReview')
  const names = ['spec-compliance', 'code-quality']
  const outcomes = await parallel(names.map((n) => () => gate(n)))
  for (const o of outcomes) {
    if (!o) continue
    const { name, v } = o
    // A gate that failed to return is itself a failed verdict — never a silent pass.
    gates[name] = isOkReturn(v, 'findings_or_observations')
      ? { verdict: v.verdict ?? 'fail', findings: v.findings_or_observations ?? [], summary: v.summary }
      : { verdict: 'fail', findings: [], summary: 'gate agent did not return a valid verdict' }
  }
} else {
  log('no changes produced — skipping two-gate self-review')
}

const bothGatesPass = ['spec-compliance', 'code-quality'].every((n) => gates[n] && gates[n].verdict === 'pass')
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
// Return the unit changes + both gate verdicts + the ledger so the main loop can gate
// on failures and decide whether to advance to its re-index/validate/commit boundary.
return { changes, gates, bothGatesPass, ledger, failed }
