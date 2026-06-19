// RUN BOUNDARY NOTE: this script performs the MCP-free annotation fan-out ONLY.
// Persisting results via `submit_annotations` is a MAIN-LOOP run boundary the
// orchestrator performs AFTER this run returns (spec §3.1, §8) — NOT here.
// Agents are MCP-free; they read ONE bundle section and return annotation JSON.
export const meta = {
  name: 'kitty-annotate',
  description: 'kitty:annotate fan-out: cartographing-kitten agents each read one bundle batch section and return per-node annotation JSON (summary/tags/role/failed). Tier per batch by args.tiers (recommended_model_tier). submit_annotations is a main-loop run boundary performed after the run, not in this script.',
  phases: [{ title: 'Annotate' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})

// ── shared schemas (mirror references/agent-output-contract.md) ──
const ANNOTATION = {
  type: 'object',
  required: ['qualified_name', 'summary', 'tags', 'role', 'failed'],
  additionalProperties: true,
  properties: {
    qualified_name: { type: 'string' },
    summary: { type: 'string' },
    tags: { type: 'array', items: { type: 'string' } },
    role: { type: 'string' },
    failed: { type: 'boolean' },
  },
}
const ANNOTATE_SCHEMA = {
  type: 'object',
  required: ['status', 'findings_or_observations'],
  additionalProperties: true,
  properties: {
    status: { type: 'string', enum: ['ok', 'bundle_unreadable', 'needs_more_context'] },
    agent: { type: 'string' },
    role: { type: 'string' },
    summary: { type: 'string' },
    confidence: { type: 'number' },
    findings_or_observations: { type: 'array', items: ANNOTATION },
  },
}

// ── per-item ledger + retry helper (spec §6) ──
const MAX_ATTEMPTS = 2
const makeLedger = (its) => its.map((it) => ({ id: it.id, status: 'pending', attempts: 0 }))
const entryFor = (ledger, id) => ledger.find((e) => e.id === id)
// A return fails if it is null/empty, throws, or has a non-ok status. `requiredKey`
// demands a shape field (the annotation array) so a schema-invalid/empty return
// counts as failed, not silently accepted (§6).
function isOkReturn(r, requiredKey) {
  if (!r || typeof r !== 'object' || Object.keys(r).length === 0) return false
  if (r.status && r.status !== 'ok') return false
  return !(requiredKey && r[requiredKey] === undefined)
}

// ── single annotation agent type (batch annotator) ──
const ANNOTATOR = 'kitty:cartographing-kitten'

const tiers = A.tiers ?? {}
const STANDARD = { model: 'sonnet', effort: 'medium' }
const lensRefs = A.lensRefs ?? {}
const bundlePath = A.bundlePath
const PROLOGUE = `First Read the bundle file at the absolute path ${bundlePath}. `
  + 'Assert it is readable and non-empty; if not, return {"status":"bundle_unreadable"} '
  + 'and stop. Read ONLY your one bundle section (the batch named below). Do not call MCP. '

// Each item is an annotation batch the orchestrator carved from the pending set.
const items = (A.items ?? []).filter((it) => it && it.id)
const ledger = makeLedger(items)

// ── annotate one batch (one cartographing-kitten over its bundle section) ──
async function annotate(item) {
  const id = item.id
  // Tier resolved by the orchestrator from recommended_model_tier; we only apply it.
  const tier = tiers[id] ?? STANDARD
  const lens = lensRefs[id] ?? ''
  const r = await agent(
    `${PROLOGUE}You are a batch annotator for the "${id}" batch. ${lens}\n`
      + 'For every node in your batch section generate a specific summary, 1-3 tags, '
      + 'and a role; set failed:true (not a guess) when a node is genuinely ambiguous. '
      + 'Apply the memory lessons section. Return an annotation envelope per '
      + 'references/agent-output-contract.md (status + findings_or_observations[]), '
      + 'each entry carrying qualified_name, summary, tags, role, failed. Do NOT call '
      + 'submit_annotations — persisting is a run boundary the orchestrator performs later.',
    { label: `annotate:${id}`, phase: 'Annotate', schema: ANNOTATE_SCHEMA, agentType: ANNOTATOR, ...tier },
  )
  return { id, result: r }
}

// ── dispatch one batch, recording the ledger (§6) ──
async function runBatch(item) {
  const entry = entryFor(ledger, item.id)
  entry.attempts += 1
  let stage
  try {
    stage = await annotate(item)
  } catch (_e) {
    stage = { id: item.id, result: null }
  }
  const r = stage && stage.result
  if (!isOkReturn(r, 'findings_or_observations')) {
    entry.status = (r && r.status === 'needs_more_context') ? 'needs_context' : 'failed'
    return { id: item.id, annotations: [] }
  }
  const raw = Array.isArray(stage.result.findings_or_observations)
    ? stage.result.findings_or_observations
    : []
  entry.status = 'done'
  return { id: item.id, annotations: raw }
}

phase('Annotate')
// A thrown/null batch thunk resolves to null → treated as failed below, never dropped.
let collected = await parallel(items.map((it) => () => runBatch(it).catch(() => null)))
for (let i = 0; i < items.length; i += 1) {
  if (!collected[i]) {
    const e = entryFor(ledger, items[i].id)
    if (e && e.status !== 'done') e.status = 'failed'
  }
}

// ── re-dispatch non-done batches, bounded by MAX_ATTEMPTS (spec §6) ──
function pending() {
  return items.filter((it) => {
    const e = entryFor(ledger, it.id)
    return e.status !== 'done' && e.attempts < MAX_ATTEMPTS
  })
}
let toRetry = pending()
while (toRetry.length > 0) {
  log(`re-dispatching ${toRetry.length} failed/needs_context batch(es)`)
  const redone = await parallel(toRetry.map((it) => () => runBatch(it).catch(() => null)))
  redone.forEach((r, i) => {
    if (r && Array.isArray(r.annotations)) {
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

// Flatten per-batch annotation arrays for the orchestrator's submit_annotations boundary.
const annotations = []
for (const c of collected) {
  if (c && Array.isArray(c.annotations)) {
    for (const a of c.annotations) annotations.push({ batch: c.id, ...a })
  }
}
const failed = ledger.filter((e) => e.status !== 'done').map((e) => e.id)
return { annotations, ledger, failed }
