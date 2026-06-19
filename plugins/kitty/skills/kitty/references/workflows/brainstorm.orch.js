export const meta = {
  name: 'kitty-brainstorm',
  description: 'kitty:brainstorm fan-out: parallel librarian-kitten research lenses (architecture and pattern) each read one bundle section and return a research envelope. Returns both lens results plus a per-lens ledger so the orchestrator can gate on failures and synthesize requirements.',
  phases: [{ title: 'Research' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})

// ── shared schema (mirror references/agent-output-contract.md) ──
// Researchers emit observation/section objects in findings_or_observations; the
// wrapper-level summary is the research-question answer.
const RESEARCH_SCHEMA = {
  type: 'object',
  required: ['status', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    agent: { type: 'string' },
    role: { type: 'string' },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array', items: { type: 'object', additionalProperties: true } },
    sources: { type: 'array', items: { type: 'object', additionalProperties: true } },
  },
}

// ── per-item ledger + retry helper (spec §6) ──
const MAX_ATTEMPTS = 2
const makeLedger = (its) => its.map((it) => ({ id: it.id, status: 'pending', attempts: 0 }))
const entryFor = (ledger, id) => ledger.find((e) => e.id === id)
// A return fails if it is null/empty, throws, or has a non-ok status. `requiredKey`
// demands a shape field (the observation array) so a schema-invalid/empty return
// counts as failed, not silently accepted (§6).
function isOkReturn(r, requiredKey) {
  if (!r || typeof r !== 'object' || Object.keys(r).length === 0) return false
  if (r.status && r.status !== 'ok') return false
  return !(requiredKey && r[requiredKey] === undefined)
}

// ── lens → agentType mapping (all research lenses share the librarian) ──
const AGENT_TYPE = {
  architecture: 'kitty:librarian-kitten',
  pattern: 'kitty:librarian-kitten',
}

const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY your one bundle section. Do not call MCP. '

// Default to the two brainstorm research lenses if the orchestrator did not name items.
const DEFAULT_LENSES = ['architecture', 'pattern']
const rawItems = (A.items ?? []).filter((it) => it && it.id)
const items = rawItems.length > 0 ? rawItems : DEFAULT_LENSES.map((id) => ({ id }))
const ledger = makeLedger(items)

// ── one research lens via librarian-kitten ──
async function research(item) {
  const lensId = item.id
  const tier = tiers[lensId] ?? STANDARD
  const lens = lensRefs[lensId] ?? ''
  const r = await agent(
    `${PROLOGUE}You are running the ${lensId} research lens. ${lens}\n`
      + 'Return a research envelope per references/agent-output-contract.md '
      + '(status + findings_or_observations[] of observation/section objects, '
      + 'wrapper-level summary answering the research question, confidence, sources).',
    { label: `research:${lensId}`, phase: 'Research', schema: RESEARCH_SCHEMA, agentType: AGENT_TYPE[lensId] ?? 'kitty:librarian-kitten', ...tier },
  )
  return { lens: lensId, result: r }
}

// ── dispatch one lens end-to-end, recording the ledger ──
async function runLens(item) {
  const entry = entryFor(ledger, item.id)
  entry.attempts += 1
  let stage
  try {
    stage = await research(item)
  } catch (_e) {
    stage = { lens: item.id, result: null }
  }
  const r = stage && stage.result
  if (!isOkReturn(r, 'findings_or_observations')) {
    entry.status = (r && r.status === 'needs_more_context') ? 'needs_context' : 'failed'
    return { lens: item.id, result: null }
  }
  entry.status = 'done'
  return { lens: item.id, result: r }
}

phase('Research')
let collected = await parallel(items.map((it) => () => runLens(it).catch(() => null)))
// A thrown/null lens thunk resolves to null → treat as failed, never dropped.
for (let i = 0; i < items.length; i += 1) {
  if (!collected[i]) {
    const e = entryFor(ledger, items[i].id)
    if (e && e.status !== 'done') e.status = 'failed'
  }
}

// ── re-dispatch non-done lenses, bounded by MAX_ATTEMPTS (spec §6) ──
function pending() {
  return items.filter((it) => {
    const e = entryFor(ledger, it.id)
    return e.status !== 'done' && e.attempts < MAX_ATTEMPTS
  })
}
let toRetry = pending()
while (toRetry.length > 0) {
  log(`re-dispatching ${toRetry.length} failed/needs_context lens(es)`)
  const redone = await parallel(toRetry.map((it) => () => runLens(it).catch(() => null)))
  redone.forEach((r, i) => {
    if (r && r.result) {
      const slot = collected.findIndex((c) => c && c.lens === toRetry[i].id)
      if (slot >= 0) collected[slot] = r
      else collected.push(r)
    } else {
      const e = entryFor(ledger, toRetry[i].id)
      if (e && e.status !== 'done') e.status = 'failed'
    }
  })
  toRetry = pending()
}

// Both lens results, keyed by lens, for orchestrator synthesis.
const lenses = {}
for (const c of collected) {
  if (c && c.lens && c.result) lenses[c.lens] = c.result
}
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
return { lenses, ledger, failed }
