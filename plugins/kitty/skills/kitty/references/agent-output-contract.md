# Unified Agent Output Contract

Every Cartographing Kittens framework subagent — annotators, researchers, and
reviewers — returns the same envelope. Skills (`kitty:plan`, `kitty:work`,
`kitty:review`, `kitty:brainstorm`) parse this envelope when synthesizing
multi-agent output. Agent-specific content lives inside
`findings_or_observations`.

```json
{
  "agent": "<agent-name>",
  "role": "annotation | research | review",
  "findings_or_observations": [
    {
      "...": "agent-specific shape (per-node annotations, per-finding objects, etc.)"
    }
  ],
  "summary": "1–3 sentence overall assessment",
  "confidence": 0.85,
  "sources": [
    {"qualified_name": "module::Class::method", "file_path": "src/module/file.py"}
  ],
  "needs_more_context": [
    {"tool": "query_node", "args": {"name": "Foo"}}
  ]
}
```

## Field semantics

| Field | Type | Notes |
|---|---|---|
| `agent` | string | Agent name as declared in `plugins/kitty/agents/manifest.json`. |
| `role` | enum | One of `annotation`, `research`, `review`. Mirrors the manifest. |
| `findings_or_observations` | list | Agent-specific payload. Reviewers emit findings; researchers emit observation/section objects; annotators emit per-node annotation entries. |
| `summary` | string | 1–3 sentences. The orchestrator surfaces this in the human-readable output. |
| `confidence` | float | 0.0–1.0. Reviewers use this for severity gating; researchers use it for synthesis weighting. |
| `sources` | list | Qualified names + file paths the agent actually read. Used for handoff-store deduplication and provenance. |
| `needs_more_context` | list | Optional. When present the orchestrator fulfills the requested tool calls and re-dispatches the agent (max one follow-up pass). |

## Per-role guidance

- **Annotators** (`cartographing-kitten`) return one entry per node in
  `findings_or_observations`, each with `qualified_name`, `summary`, `tags`,
  `role`, and `failed`. Skip the wrapper's `confidence` field — annotators
  return per-node confidence inside each entry instead.
- **Researchers** (the four `librarian-kitten-*`) return observation
  sections — `Technology & stack`, `Architecture`, `Patterns`, `Key files`,
  `Dependencies`, `Conventions`, `Memory lessons` — encoded as objects in
  `findings_or_observations`. The wrapper-level `summary` is the
  research-question answer.
- **Reviewers** (the four `expert-kitten-*`) return findings — each with
  `severity` (`P0`–`P3`), `category`, `location`, `issue`, `guidance`,
  `confidence`, and `autofix_class`. The wrapper-level `confidence` is
  optional; per-finding confidence is what gates severity.

## Why a unified envelope?

Skills compact agent prose into the persistent handoff store
(`agent_handoffs` table) and pass `run_id`s instead of the full prose into
follow-up agent prompts. A common envelope means the orchestrator can:

- Drop `cleanable: true` raw graph payloads on compaction without losing
  agent conclusions.
- Look up findings/observations by `run_id` when synthesizing.
- Trace provenance through `sources` rather than re-scanning prose.

This contract is pinned at the framework level so skill orchestrators do not
reinvent a parsing layer per agent.
