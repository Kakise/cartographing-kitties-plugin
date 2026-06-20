export const meta = {
  name: 'kitty-review',
  description: 'kitty:review fan-out: per-dimension reviewer agents read one bundle section and return findings; P0/P1 findings are adversarially re-verified at the hard tier before being kept. Always-on correctness/testing; conditional impact/structure/context.',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
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
const REVIEW_SCHEMA = {
  type: 'object',
  required: ['status', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    agent: { type: 'string' },
    role: { type: 'string' },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array', items: FINDING },
  },
}
const VERIFY_SCHEMA = {
  type: 'object',
  required: ['status', 'real'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    real: { type: 'boolean' },
    rationale: { type: 'string' },
    confidence: { type: 'number' },
  },
}

// ── per-item ledger + retry helper (spec §6) ──
const MAX_ATTEMPTS = 2
const makeLedger = (its) => its.map((it) => ({ id: it.id, status: 'pending', attempts: 0 }))
const entryFor = (ledger, id) => ledger.find((e) => e.id === id)
// A return fails if it is null/empty, throws, or has a non-ok status. `requiredKey`
// demands a shape field (the reviewer's findings array) so a schema-invalid/empty
// return counts as failed, not silently accepted (§6).
function isOkReturn(r, requiredKey) {
  if (!r || typeof r !== 'object' || Object.keys(r).length === 0) return false
  if (r.status && r.status !== 'ok') return false
  return !(requiredKey && r[requiredKey] === undefined)
}

// ── dimension → agentType mapping ──
const AGENT_TYPE = {
  correctness: 'kitty:expert-kitten-correctness',
  testing: 'kitty:expert-kitten-testing',
  impact: 'kitty:expert-kitten-impact',
  structure: 'kitty:expert-kitten-structure',
  context: 'kitty:expert-kitten-context',
}

const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const HARD_VERIFY = tiers.verify ?? { model: 'opus', effort: 'xhigh' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY your one bundle section. Do not call MCP. '

// Always-on dimensions plus any conditional dimension the orchestrator marked active.
const items = (A.items ?? []).filter((it) => it && it.id)
const ledger = makeLedger(items)

// ── Stage 1: reviewer agent for one dimension ──
async function review(item) {
  const dim = item.id
  const tier = tiers[dim] ?? STANDARD
  const lens = lensRefs[dim] ?? ''
  const r = await agent(
    `${PROLOGUE}You are the ${dim} reviewer. ${lens}\n`
      + 'Return a findings envelope per references/agent-output-contract.md '
      + '(status + findings_or_observations[]). Each finding needs severity, category, '
      + 'location, issue, guidance, confidence, autofix_class.',
    { label: `review:${dim}`, phase: 'Review', schema: REVIEW_SCHEMA, agentType: AGENT_TYPE[dim], ...tier },
  )
  return { dim, result: r }
}

// ── Stage 2: adversarial verification of each P0/P1 finding (hard tier) ──
async function verifyFindings(dim, findings) {
  const high = findings.filter((f) => f && (f.severity === 'P0' || f.severity === 'P1'))
  const low = findings.filter((f) => f && f.severity !== 'P0' && f.severity !== 'P1')
  const verdicts = await parallel(
    high.map((f) => () =>
      agent(
        `${PROLOGUE}Adversarially verify this ${dim} finding. Is it a REAL defect, or a `
          + 'false positive? Return {"status":"ok","real":<bool>,"rationale":...}. '
          + `Finding: ${JSON.stringify({ severity: f.severity, location: f.location, issue: f.issue })}`,
        { label: `verify:${dim}:${f.severity}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: AGENT_TYPE[dim], ...HARD_VERIFY },
      ).then((v) => ({ f, v })).catch(() => ({ f, v: null })),
    ),
  )
  // Keep a high-severity finding only if its verifier survives and confirms real === true.
  const survived = []
  for (const outcome of verdicts) {
    if (!outcome) continue
    const { f, v } = outcome
    if (isOkReturn(v) && v.real === true) survived.push(f)
  }
  return low.concat(survived)
}

// ── dispatch one dimension end-to-end (review → verify), recording the ledger ──
async function runDimension(item) {
  const entry = entryFor(ledger, item.id)
  entry.attempts += 1
  let stage1
  try {
    stage1 = await review(item)
  } catch (_e) {
    stage1 = { dim: item.id, result: null }
  }
  const r1 = stage1 && stage1.result
  if (!isOkReturn(r1, 'findings_or_observations')) {
    entry.status = (r1 && r1.status === 'needs_more_context') ? 'needs_context' : 'failed'
    return { dim: item.id, findings: [] }
  }
  const raw = Array.isArray(stage1.result.findings_or_observations)
    ? stage1.result.findings_or_observations
    : []
  let kept = []
  try {
    kept = await verifyFindings(item.id, raw)
  } catch (_e) {
    entry.status = 'failed'
    return { dim: item.id, findings: [] }
  }
  entry.status = 'done'
  return { dim: item.id, findings: kept }
}

phase('Review')
let collected = await parallel(items.map((it) => () => runDimension(it).catch(() => null)))
// A thrown/null dimension thunk resolves to null → treat as failed, never dropped.
for (let i = 0; i < items.length; i += 1) {
  if (!collected[i]) {
    const e = entryFor(ledger, items[i].id)
    if (e && e.status !== 'done') e.status = 'failed'
  }
}

// ── re-dispatch non-done items, bounded by MAX_ATTEMPTS (spec §6) ──
function pending() {
  return items.filter((it) => {
    const e = entryFor(ledger, it.id)
    return e.status !== 'done' && e.attempts < MAX_ATTEMPTS
  })
}
let toRetry = pending()
while (toRetry.length > 0) {
  log(`re-dispatching ${toRetry.length} failed/needs_context dimension(s)`)
  const redone = await parallel(toRetry.map((it) => () => runDimension(it).catch(() => null)))
  redone.forEach((r, i) => {
    if (r && Array.isArray(r.findings)) {
      const slot = collected.findIndex((c) => c && c.dim === toRetry[i].id)
      if (slot >= 0) collected[slot] = r
      else collected.push(r)
    } else {
      const e = entryFor(ledger, toRetry[i].id)
      if (e && e.status !== 'done') e.status = 'failed'
    }
  })
  toRetry = pending()
}

const findings = []
for (const c of collected) {
  if (c && Array.isArray(c.findings)) {
    for (const f of c.findings) findings.push({ dimension: c.dim, ...f })
  }
}
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
return { findings, ledger, failed }
