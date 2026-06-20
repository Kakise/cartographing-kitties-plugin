export const meta = {
  name: 'kitty-plan',
  description: 'kitty:plan research fan-out: the four librarian lenses (architecture, pattern, flow, impact) run in parallel as kitty:librarian-kitten agents, each reading one bundle section with its injected lens text, and return per-lens observations for the orchestrator to synthesize into a plan. Ledger over the 4 lenses; failed lenses re-dispatched, never dropped.',
  phases: [{ title: 'Research' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})

// ── shared schema (mirror references/agent-output-contract.md research envelope) ──
const OBSERVATION = {
  type: 'object',
  required: ['section', 'content'],
  additionalProperties: true,
  properties: {
    section: { type: 'string' },
    content: { type: 'string' },
  },
}
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
    sources: { type: 'array', items: { type: 'object', additionalProperties: true } },
    findings_or_observations: { type: 'array', items: OBSERVATION },
  },
}

// ── per-item ledger + retry helper (spec §6) ──
const MAX_ATTEMPTS = 2
const makeLedger = (its) => its.map((it) => ({ id: it.id, status: 'pending', attempts: 0 }))
const entryFor = (ledger, id) => ledger.find((e) => e.id === id)
// A return fails if it is null/empty, throws, or has a non-ok status. `requiredKey`
// demands a shape field (the researcher's observations array) so a schema-invalid/empty
// return counts as failed, not silently accepted (§6).
function isOkReturn(r, requiredKey) {
  if (!r || typeof r !== 'object' || Object.keys(r).length === 0) return false
  if (r.status && r.status !== 'ok') return false
  return !(requiredKey && r[requiredKey] === undefined)
}

// ── lens → agentType mapping (all four lenses share the consolidated librarian) ──
const AGENT_TYPE = {
  architecture: 'kitty:librarian-kitten',
  pattern: 'kitty:librarian-kitten',
  flow: 'kitty:librarian-kitten',
  impact: 'kitty:librarian-kitten',
}

const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY your one bundle section. Do not call MCP. '

// The four research lenses (plus any the orchestrator marked active in args.items).
const items = (A.items ?? []).filter((it) => it && it.id)
const ledger = makeLedger(items)

// ── research agent for one lens ──
async function research(item) {
  const lensName = item.id
  const tier = tiers[lensName] ?? STANDARD
  const lens = lensRefs[lensName] ?? ''
  const r = await agent(
    `${PROLOGUE}You are running the ${lensName} lens. ${lens}\n`
      + 'Return a research envelope per references/agent-output-contract.md '
      + '(status + findings_or_observations[]). Encode each observation as an object '
      + 'with a section name and its content; set the wrapper summary to the '
      + 'research-question answer for this lens.',
    { label: `research:${lensName}`, phase: 'Research', schema: RESEARCH_SCHEMA, agentType: AGENT_TYPE[lensName], ...tier },
  )
  return { lens: lensName, result: r }
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
    return { lens: item.id, observations: [], summary: '', confidence: undefined, sources: [] }
  }
  entry.status = 'done'
  return {
    lens: item.id,
    observations: Array.isArray(r.findings_or_observations) ? r.findings_or_observations : [],
    summary: typeof r.summary === 'string' ? r.summary : '',
    confidence: r.confidence,
    sources: Array.isArray(r.sources) ? r.sources : [],
  }
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
    if (r && Array.isArray(r.observations)) {
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

const lenses = []
for (const c of collected) {
  if (c && Array.isArray(c.observations)) {
    lenses.push({
      lens: c.lens,
      summary: c.summary,
      confidence: c.confidence,
      observations: c.observations,
      sources: c.sources,
    })
  }
}
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
return { lenses, ledger, failed }
