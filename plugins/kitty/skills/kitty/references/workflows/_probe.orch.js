export const meta = {
  name: 'kitty-probe',
  description: 'One-time probe: does agent({model}) actually route the child model?',
  phases: [{ title: 'Probe' }],
}
const A = typeof args === 'string' ? JSON.parse(args) : (args ?? {})
const SCHEMA = {
  type: 'object', required: ['reported_model', 'evidence'], additionalProperties: false,
  properties: { reported_model: { type: 'string' }, evidence: { type: 'string' } },
}
const ask = 'State your exact underlying model id (e.g. claude-haiku-4-5, claude-opus-4-8). '
  + 'Then in one sentence give any evidence you can about which model you are. Return per schema.'
phase('Probe')
const tiers = ['haiku', 'sonnet', 'opus']
const out = await parallel(tiers.map((m) => () =>
  agent(ask, { label: `probe:${m}`, phase: 'Probe', schema: SCHEMA, model: m })
    .then((r) => ({ requested: m, ...r }))))
return { results: out.filter(Boolean) }
