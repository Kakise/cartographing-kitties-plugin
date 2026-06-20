export const meta = {
  name: 'kitty-impact',
  description: 'kitty:impact fan-out: a single librarian-kitten reads the blast-radius bundle under the impact lens and returns an impact-summary envelope (direct and transitive dependents, affected tests, cross-boundary risk, overall risk). Tier by blast_radius.',
  phases: [{ title: 'Impact' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})

// ── shared schema (mirror references/agent-output-contract.md research envelope) ──
// Librarians emit observation/section objects in findings_or_observations; the
// wrapper-level summary is the research-question answer (here, the blast radius).
const OBSERVATION = {
  type: 'object',
  required: ['section', 'detail'],
  additionalProperties: true,
  properties: {
    section: { type: 'string' },
    detail: { type: 'string' },
  },
}
const IMPACT_SCHEMA = {
  type: 'object',
  required: ['status', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    agent: { type: 'string' },
    role: { type: 'string' },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array', items: OBSERVATION },
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

// ── tier application (orchestrator resolves; the script only applies args.tiers) ──
const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY the Dependents (blast-radius) bundle section. Do not call MCP. '

const items = (A.items ?? []).filter((it) => it && it.id)
const ledger = makeLedger(items)

// ── single librarian dispatch over the blast-radius bundle, under the impact lens ──
async function analyze(item) {
  const tier = tiers[item.id] ?? tiers.impact ?? STANDARD
  const lens = lensRefs.impact ?? lensRefs[item.id] ?? ''
  const r = await agent(
    `${PROLOGUE}You are running the impact lens over the blast-radius bundle. ${lens}\n`
      + 'Assess the blast radius of the change in scope using the pre-computed dependent '
      + 'data. Categorize dependents by depth (direct vs transitive), group by role/tag, '
      + 'flag affected test files and cross-boundary risk, and weigh edge-kind risk '
      + '(inherits > imports > calls). Return a research envelope per '
      + 'references/agent-output-contract.md: status + findings_or_observations[] '
      + '(one observation per section: Symbols analyzed, Direct dependents, Transitive '
      + 'dependents, Affected tests, Cross-boundary risks, Memory lessons, Risk assessment), '
      + 'with the wrapper summary stating the overall blast radius and Low/Medium/High risk.',
    { label: `impact:${item.id}`, phase: 'Impact', schema: IMPACT_SCHEMA, agentType: 'kitty:librarian-kitten', ...tier },
  )
  return { id: item.id, result: r }
}

// ── dispatch one item, recording the ledger (spec §6) ──
async function runItem(item) {
  const entry = entryFor(ledger, item.id)
  entry.attempts += 1
  let stage
  try {
    stage = await analyze(item)
  } catch (_e) {
    stage = { id: item.id, result: null }
  }
  const r = stage && stage.result
  if (!isOkReturn(r, 'findings_or_observations')) {
    entry.status = (r && r.status === 'needs_more_context') ? 'needs_context' : 'failed'
    return { id: item.id, result: null }
  }
  entry.status = 'done'
  return { id: item.id, result: r }
}

phase('Impact')
let collected = await parallel(items.map((it) => () => runItem(it).catch(() => null)))
// A thrown/null item thunk resolves to null → treat as failed, never dropped.
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
  log(`re-dispatching ${toRetry.length} failed/needs_context item(s)`)
  const redone = await parallel(toRetry.map((it) => () => runItem(it).catch(() => null)))
  redone.forEach((r, i) => {
    if (r && r.result) {
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

const summaries = []
for (const c of collected) {
  if (c && c.result) {
    summaries.push({
      id: c.id,
      summary: c.result.summary,
      confidence: c.result.confidence,
      observations: Array.isArray(c.result.findings_or_observations)
        ? c.result.findings_or_observations
        : [],
    })
  }
}
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
return { summaries, ledger, failed }
