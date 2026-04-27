# Harness Overhaul — Context Engineering, Skill/Agent Specialization, Codex Parity

Brainstorm date: 2026-04-27
Triggered by: "Improve this plugin as a whole — reduce context rot, enhance skills, enhance agents, ensure Codex + Claude Code parity."

## Problem Frame

Cartographing Kittens has correctly bet on a graph-first model and a portable inline-with-optional-delegation execution posture. The problem isn't the bet — it's the *harness layer that exposes the bet to agents*: the SKILL.md prompts, the agent definitions, the MCP tool surface, and the Codex/Claude Code packaging.

Three specific pressures the current harness does not yet address:

1. **Context rot is a real, measurable phenomenon and the harness is not engineered against it.** Anthropic's Sept 2025 guidance is explicit: "treat context as a finite resource with diminishing marginal returns" and "find the smallest possible set of high-signal tokens." The current harness ships a 700-line `tool-reference.md`, four agents that each duplicate `subgraph-context-format.md`, MCP tools that return raw rows with no token budget, and skills 200–400 lines long. There is no compaction protocol, no tool-result-clearing pattern, no response-budget contract on MCP tools, no progressive disclosure inside the bigger skills.
2. **Skills and agents under-use the official extension points of the runtimes they target.** Claude Code skills support `paths`, `context: fork`, `agent`, `disable-model-invocation`, `allowed-tools`, `model`, `effort`, `!command` dynamic context injection, `${CLAUDE_SKILL_DIR}`, and indexed `$N` arguments. Codex has first-class TOML subagents under `.codex/agents/` with `[agents] max_threads`, `max_depth`, `job_max_runtime_seconds` config, and skill-scoped `agents/openai.yaml`. The current plugin uses almost none of these — frontmatter is limited to `name`, `description`, occasionally `argument-hint` and `disable-model-invocation`.
3. **Codex is treated as a second-class runtime.** `manifest.json` declares the agents, but Codex execution is inline-only because the plugin ships no `.codex/agents/*.toml` files. Codex has had real subagent support since early 2026 and the plugin is leaving that capability on the table. The repo also fragments per-runtime — `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`, `manifest.json` — each maintained by hand, with drift risk.

This brainstorm is **not** about new graph capabilities (that is `2026-04-23-001-plugin-evolution`'s job), and **not** about extracting skills into a separate repo (that is `2026-04-27-001-skills-submodule-repository`'s job). It is about making the harness layer that wraps the existing graph dramatically more efficient per token, more explicit per runtime, and more self-consistent.

## Codebase Context

Verified against the live graph (1040 nodes, 778 annotated, 0 stale; agent-explorer pass on every skill and agent file):

### Skill layer — `plugins/kitty/skills/`
- 9 skills: `kitty` (router, ~300 lines + 4 references totalling ~1,270 lines), `kitty-brainstorm` (~200), `kitty-plan` (~350), `kitty-work` (~250), `kitty-review` (~400), `kitty-explore` (~120), `kitty-impact` (~130), `kitty-annotate` (~100), `kitty-lfg` (~50).
- All skills use only `name` + `description` + occasionally `argument-hint`. No skill uses `paths`, `allowed-tools`, `context: fork`, `agent`, `model`, `effort`, or `!command` dynamic context injection.
- `kitty/SKILL.md` references four files in `references/`: `tool-reference.md` (~700 lines), `annotation-workflow.md` (~200), `subgraph-context-format.md` (~250), `memory-workflow.md` (~120).
- `kitty-review` is densely informative but at 400 lines is past Anthropic's 500-line soft cap and has 8 stages with no internal `references/` to defer detail.
- `kitty-lfg` is 50 lines and underspecified — does not gate on runtime support, does not document failure recovery, has `disable-model-invocation: true` without explaining why.

### Agent layer — `plugins/kitty/agents/`
- 9 agents declared via `manifest.json` with `runtime` field: `claude_code (directory-discovered)` + `codex (framework-declared, inline)`. Codex never spawns these as real subagents.
- Agent prompts use `name`, `model: inherit`, `tools: Read, Grep, Glob, Bash`, custom `framework_status: active-framework-agent`, occasionally `color`. They do not use Claude Code's `tools` allowlist precisely (most agents could be `Read, Grep, Glob` only — no Bash needed for review/research) nor declare a model (Sonnet would be cheaper than inherit-from-Opus for most agent work — Anthropic's reference architecture is Opus lead + Sonnet subagents).
- Agent expected-context sections duplicate `subgraph-context-format.md`. Two sources of truth.
- "Preserved framework subagents" is referenced in skills but never enumerated; readers must cross-check `manifest.json`.

### MCP layer — `src/cartograph/server/`
- 21 tools across `index.py`, `query.py`, `analysis.py`, `annotate.py`, `memory.py`, `reactive.py`. Above MCP's "8–12 tools is reasonable" guideline.
- No tool declares `outputSchema`/`structuredContent` (June 2025 spec). All return free-form JSON.
- No tool accepts a `token_budget`, `response_shape` ("compact"/"full"), `cursor`, or `max_tokens` parameter. `search`, `get_file_structure`, `query_node`, `find_dependents`, `find_dependencies`, `rank_nodes`, `batch_query_nodes` can all return arbitrarily large payloads.
- `query_node` returns full neighbors with no caller hint about how many to return; on hub nodes (`get_store`, `_make_node`) this can be 50+ items.
- No "compact" mode that returns just `qualified_name + summary + role + score`. The skill-side `subgraph-context-format.md` re-shapes raw responses into compact structured text; this re-shaping should live in the MCP server, not in every skill.

### Packaging — `plugins/kitty/`
- Four manifests maintained by hand: `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `gemini-extension.json`, `agents/manifest.json`. Plus `.mcp.json`. Plus the soon-to-exist Codex `.codex/agents/*.toml` (this RFC).
- `2026-04-27-001-skills-submodule-repository` is moving skills toward a JetBrains-style standalone catalog repo. This RFC's changes must be compatible with that move (single source-of-truth, generators, validators).

## Cross-References

- **`2026-04-23-001-plugin-evolution`** (capability evolution: hybrid retrieval, LSP, multi-dim graph, multi-language). This RFC depends on no Tier-1 work from that doc; the harness improvements ship independently. But: if this RFC introduces compact response shapes on MCP tools (R5), those shapes should accommodate future embedding-rank scores so `2026-04-23-001`'s R1 doesn't require a second contract change.
- **`2026-04-27-001-skills-submodule-repository`** (extract skills into a JetBrains-compatible catalog repo). Compatible: this RFC's frontmatter additions and `references/` extractions are still valid skills under the JetBrains layout. The agent generator (R7) and the manifests-from-source-of-truth contract (R8) should land in this repo first and then move with the skills if/when extracted.

## Requirements

Themes are tiered by `(impact_on_token_efficiency × runtime_correctness) / implementation_cost`. Each requirement is testable so `kitty:plan` can pick any subset and spec it concretely.

### Tier 1 — Context engineering at the MCP boundary

The MCP server is the single largest source of tokens flowing into agents. Shape the responses there once and every skill, agent, and runtime benefits.

- **R1. Add `outputSchema` and `structuredContent` to all `query.py` and `analysis.py` tools.** Per the June 2025 MCP spec, tools should expose typed schemas. Test: every tool registered in `cartograph.server.main` has a non-empty `outputSchema`; integration tests parse responses against the schema.
- **R2. Add a `response_shape` parameter to high-traffic query tools.** `query_node`, `get_file_structure`, `find_dependencies`, `find_dependents`, `search`, `rank_nodes`, `batch_query_nodes` accept `response_shape: "compact" | "standard" | "full"` (default `"standard"`). `compact` returns only `qualified_name`, `kind`, `role`, `summary` (truncated at 160 chars), `centrality`. `full` adds raw neighbors, file path, line range. Test: requesting `compact` on a hub node (`get_store`, in_degree=18) returns ≤2,000 tokens; requesting `full` is unrestricted but emits a `truncated: true` flag if the response would exceed an internal soft cap (default 8,000 tokens).
- **R3. Add a `token_budget` parameter to every tool that can return >1,000 tokens.** When passed, the server is *required* to keep the response under the budget — by truncating, paginating, or compacting — and must include a `budget_used`, `budget_remaining`, and `truncated_items` count. Test: `search(query="x", limit=200, token_budget=1500)` returns ≤1,500 tokens with a populated `truncated_items`.
- **R4. Pagination via cursors on `search`, `find_dependents`, `find_dependencies`, `batch_query_nodes`, `rank_nodes`.** Each returns `next_cursor: str | null`; cursors are opaque base64-encoded offsets the server validates. Test: paginating through `search` returns the same total set as `limit=large` would.
- **R5. Tool consolidation: collapse near-duplicate tools into one, behind an enum.** `find_dependencies` and `find_dependents` keep separate names (different mental models) but share a `_traverse` implementation taking a `direction` arg. Audit `analysis.py` for any pair where the only difference is direction or kind. The 21-tool surface should shrink toward the 8–12 sweet spot or remain at 21 only if every tool has a clearly distinct mental model. Test: `kitty:explore` and `kitty:impact` skills can be re-written without losing capability after the consolidation.
- **R6. Tool-result clearing protocol.** The MCP server adds an optional `cleanable: true` hint to responses for tool results that are safe to drop from history once consumed (e.g., `index_codebase` summary, `validate_graph` health check, intermediate `get_file_structure` reads that have been distilled into a higher-level summary). Skills and agents read the hint and explicitly summarize-then-discard rather than carrying the raw payload. Test: a skill that calls `get_file_structure` ten times across an exploration run leaves at most one raw payload in context after compaction.

### Tier 2 — Skill architecture: progressive disclosure inside skills

Skills should follow the same frontmatter→references pattern Claude Code recommends, applied inside our own large skills.

- **R7. Every skill ≥250 lines is split.** `SKILL.md` keeps the orchestration spine + frontmatter + decision tree; bulky stage detail moves into a co-located `references/` folder with explicit pointers. Targets: `kitty-review` → `references/{review-stages.md, severity-and-autofix.md, output-format.md}`; `kitty-plan` → `references/{plan-format.md, research-synthesis.md, confidence-checklist.md}`; `kitty/SKILL.md` is already split correctly, but `references/tool-reference.md` (700 lines) is itself split by tool family (`query.md`, `analysis.md`, `annotate.md`, `memory.md`, `reactive.md`). Test: every `SKILL.md` is ≤500 lines (Anthropic's stated cap); no skill loses information.
- **R8. Use the full Claude Code frontmatter spectrum.**
  - `paths` on `kitty:annotate` (only auto-load when working with `*.py`/`*.ts`/`*.js` files), `kitty:explore` (when `src/`, `lib/`, `app/` files are touched), `kitty:work` (when `docs/plans/*.md` is in scope), `kitty:review` (when a diff is present).
  - `allowed-tools` on every skill — listing exactly the MCP tools and built-ins the skill needs. This both pre-approves them and documents the contract.
  - `disable-model-invocation: true` on `kitty:lfg` (already present), `kitty:work`, `kitty:annotate` (these mutate state — Claude shouldn't auto-trigger them).
  - `argument-hint` on every skill, even simple ones, for autocomplete.
  - Test: every skill has at least `paths` (where applicable), `allowed-tools`, and `argument-hint` populated; spot-check that `paths` filters work in a real session.
- **R9. Use `!command` dynamic context injection where it kills a manual step.** `kitty:review` can inject `!`git diff --name-only HEAD~1`` and `!`git log -1 --pretty=%B`` so the reviewer prompt arrives with diff scope already populated. `kitty:work` can inject `!`uv run pytest --collect-only -q | head -20`` so the worker sees what tests exist before implementing. `kitty:lfg` can inject the active branch and recent commits. Test: dry-run a skill invocation and confirm the rendered prompt contains the live shell output, not the literal command.
- **R10. Compaction-resilient skills.** Anthropic's docs reveal: after compaction, only the first 5,000 tokens of each invoked skill survive, and the most-recent skills win the 25,000-token shared budget. Therefore: every skill puts its decision tree, tool selection matrix, and contract in the *first* 5,000 tokens; longer detail goes to references. Stage-by-stage walkthrough should be summarisable; if the first 5,000 tokens dropped the rest, the skill must still produce a correct (if rougher) output. Test: truncate each `SKILL.md` to 5,000 tokens and dry-run — workflow phases must still be identifiable, the decision tree must be intact.
- **R11. Promote sub-skills as bundled skills, not as router-internal references.** `kitty:explore`, `kitty:impact`, `kitty:annotate` already exist as standalone skills. The router skill (`kitty/SKILL.md`) should *delegate* (with `Skill` tool calls or explicit "use skill X" instructions) rather than carry an inline router-and-tool-reference monolith. Test: `kitty/SKILL.md` shrinks below 200 lines and reads as a routing manifest, not a procedure.

### Tier 3 — Agent specialization

Specialized agents with isolated contexts are Anthropic's documented pattern. The current agents are well-organized but under-specialized in three ways: tool permissions are too broad, output contracts are inconsistent, and they don't carry scaling-rule prompts to prevent over-spawning.

- **R12. Tighten tool permissions per agent role.**
  - Researcher agents (`librarian-kitten-*`): `Read, Grep, Glob` only — they do not need `Bash`. Add MCP tool allowlist explicitly: `mcp__plugin_kitty_kitty__query_node`, `__search`, `__get_file_structure`, `__find_dependencies`, `__find_dependents`, `__rank_nodes`.
  - Reviewer agents (`expert-kitten-*`): `Read, Grep, Glob` + the same MCP allowlist. No write tools.
  - Annotator agent (`cartographing-kitten`): `Read, Grep, Glob, Bash` (Bash for one-off `git log` sanity checks) + MCP `__query_node`, `__get_file_structure`.
  - Test: every agent's `tools` field is the smallest set that lets it complete its job; deny-by-default for everything else.
- **R13. Default `model: claude-sonnet-4-6` for all agents; reserve Opus for the orchestrator.** Anthropic's reference: Opus lead + Sonnet subagents matched single-Opus on quality at a fraction of the cost. The current `model: inherit` passes Opus down. Add an opt-out comment for cases that genuinely need Opus depth (none currently). Test: a parallel review run with 4 agents on Sonnet costs ≤25% of a parallel review run on inherit-Opus.
- **R14. Embed scaling rules in every research-agent prompt.** Anthropic's multi-agent paper documents agents spawning 50 subagents for trivial queries. Each `librarian-kitten-*` prompt gets a calibration block: "Simple lookup → 1–3 tool calls. Direct comparison → 5–10 tool calls. Complex architectural pass → 10–20 tool calls. Stop when you have a confident answer; do not exhaust the search space." Test: the prompts contain a verbatim scaling rubric and an explicit stop condition.
- **R15. Unify agent output contracts.** Reviewer agents already return JSON (`reviewer`, `findings[]`, `summary`). Researcher and pattern agents return free-form prose. Standardise: every agent returns `{role, findings_or_observations: [...], summary, confidence, sources: [...]}`. `sources` is a list of qualified names + file paths the agent looked at — supports the lead's synthesis and lets the lead cite. Test: every agent's "Output contract" section in its `.md` matches the schema; a review and a research run both produce parseable JSON.
- **R16. Stop duplicating `subgraph-context-format.md` inside each agent.** Each agent prompt removes its inline expected-context section and links to the canonical reference. The orchestrator continues to pre-format. Test: searching for "annotation status" or "target nodes" finds exactly one source-of-truth file.
- **R17. Document the agent-spawn map explicitly in `kitty/SKILL.md`.** A table: `(skill, condition) → agents spawned`. Replaces the current implicit "preserved framework subagents" phrasing. Test: every skill that may spawn an agent points at the table; every agent in `manifest.json` appears in the table or is explicitly marked unused.
- **R18. Add an `expert-kitten-context` reviewer.** New always-on reviewer that flags the *prompt itself* — token count, redundancy with prior context, missing structured handoff. Reviews the orchestrator's pre-formatted subgraph context before the heavyweight reviewers run. Optional, but it would catch context drift early. Test: invoking `kitty:review` on a synthetic large diff reports a context-budget finding.

### Tier 4 — Codex first-class runtime parity

The user-confirmed direction: real `.codex/agents/*.toml` files, generated from a single source of truth alongside Claude Code `.md` files.

- **R19. Define a single source-of-truth agent format.** A neutral YAML/TOML/JSON file per agent under `plugins/kitty/agents/_source/<agent>.yaml` containing: `name`, `description`, `role`, `model`, `tools` (allowlist), `mcp_tools`, `developer_instructions`, `output_contract`, `scaling_rules`, `expected_context_pointer`. Test: `manifest.json`, Claude Code `.md`, and Codex `.toml` are all generated from `_source/` files; CI fails if generated files drift from source.
- **R20. Generator script `scripts/generate_agents.py`.** Reads `_source/`, emits `plugins/kitty/agents/<name>.md` (Claude Code), `plugins/kitty/.codex/agents/<name>.toml` (Codex), and updates `plugins/kitty/agents/manifest.json`. Idempotent. Test: `uv run python scripts/generate_agents.py` produces no diff on a clean repo; deleting a generated file and re-running restores it byte-identically.
- **R21. Wire Codex `[agents]` config.** Add `plugins/kitty/.codex/config.toml` (or document the recommended user-side `~/.codex/config.toml` block) with `max_threads = 4`, `max_depth = 1`, `job_max_runtime_seconds = 300`. The plugin's skills can rely on these limits when they say "spawn N parallel agents." Test: `kitty:review` with 4 reviewer agents under Codex completes within `max_threads`; documented in the skill.
- **R22. Codex `agents/openai.yaml` per skill (where useful).** Skills that need Codex-specific UI metadata or invocation policy (`allow_implicit_invocation: false` on `kitty:lfg`, `kitty:work`) ship a co-located `agents/openai.yaml`. Test: the file is valid YAML and Codex picks it up.
- **R23. AGENTS.md upgrade.** Codex reads `AGENTS.md` for repo-level rules. The current `AGENTS.md` is deleted in `git status`; restore and align it with `CLAUDE.md`'s contract: same conventions, same Cartographing-Kittens-first principle, same `KITTY_STORAGE_ROOT` hint, but Codex-flavored examples (`codex` commands, `.codex/agents/*` paths). Test: `AGENTS.md` exists; `CLAUDE.md` and `AGENTS.md` are kept in sync via a generator or a CI lint.
- **R24. Plugin manifests generated from one config.** `plugins/kitty/.claude-plugin/plugin.json`, `plugins/kitty/.codex-plugin/plugin.json`, `plugins/kitty/gemini-extension.json` are emitted from a single `plugins/kitty/_meta/plugin.yaml`. Test: editing the source bumps all three manifests; CI validates JSON Schema for each.

### Tier 5 — Memory + handoff

Anthropic's multi-agent paper makes a sharp point: subagents writing results to a *filesystem* and returning lightweight refs to the lead is more faithful than passing 10k-token prose. Cartographing Kittens already has memory (litter-box / treat-box) and a graph; we can extend the same idea.

- **R25. Persistent agent-handoff store.** New table in the memory DB (`agent_handoffs`) — keyed by `session_id + agent_name + run_id`. Agents write `findings`, `notes`, `sources` rows; the lead reads back via a new MCP tool `get_agent_handoff(run_id)`. The lead's prompt only carries the `run_id`, not the prose. Test: a 4-agent review writes 4 handoff records; the lead synthesizes from them via tool calls, not from in-prompt prose.
- **R26. Compaction protocol on the orchestrator side.** When the conversation nears its token budget, the lead invokes a new skill `kitty:compact` (or built-in compaction) that: (a) preserves the active plan/requirements doc reference, (b) replaces raw tool outputs with `get_agent_handoff` references, (c) drops `cleanable: true` MCP responses entirely, (d) keeps the most recent `query_node`/`get_file_structure` calls only for files currently being worked on. Test: a long run that triggers compaction retains the plan, the agent handoffs, and the active file context; loses only the raw intermediate query payloads.
- **R27. Memory queries are budgeted.** `query_litter_box` and `query_treat_box` accept `token_budget` and a relevance score (e.g., FTS5 ranking) to surface the most relevant lessons first. Test: a `kitty:work` preflight pulling 50 treat-box entries returns under 2,000 tokens.

### Tier 6 — Observability, validation, and tests

The harness should be testable from the outside. Today, drift between `tool-reference.md` and the real MCP surface is invisible until an agent fails.

- **R28. Skill validator.** `scripts/validate_skills.py` runs in CI and asserts: every `SKILL.md` ≤500 lines; frontmatter has `name`, `description` (≤1,536 chars combined with `when_to_use`), and `argument-hint`; `allowed-tools` references real tools; `paths` globs are syntactically valid; `references/*.md` files referenced in `SKILL.md` exist.
- **R29. Tool-reference autogeneration.** `references/tool-reference.md` (split per R7) is generated from the FastMCP server's introspected tool registry. Test: running the generator on a clean repo produces no diff; adding a tool to the server adds a stub to the reference and fails CI until the stub is filled in.
- **R30. Telemetry hook.** Skills emit a structured `kitty.telemetry.json` line per run — skill name, duration, tool calls, tokens (if measurable), agents spawned, exit status. Aggregate over time to find which skills are over-budget. Test: a `kitty:review` run produces a telemetry line; the line schema is fixed.
- **R31. Hooks for invariants.** Use Claude Code `hooks` (PreToolUse / PostToolUse) and Codex hooks to enforce: index-before-querying (auto-run `index_codebase` if `validate_graph` reports `stale > 0`), memory-preflight on workflow skills (auto-run `query_litter_box` / `query_treat_box` if not invoked), recompute centrality after structural changes. Test: deleting the graph and invoking `kitty:explore` triggers a SessionStart hook that re-indexes; configured in `plugins/kitty/hooks/`.
- **R32. Smoke tests per skill.** A pytest fixture invokes each skill via the MCP server's prompt machinery on a 50-file fixture project and asserts: workflow completes, expected files are written (e.g., `docs/brainstorms/*-requirements.md`), telemetry lines emitted. Test: `uv run pytest tests/test_skill_smoke.py` passes for all 9 skills.

## Success Criteria

A v2 release is shipped when:

- **Token efficiency** — On a fixed 50-file fixture project, the median `kitty:review` run measures **≤50% of the current run's input-token consumption** in the orchestrator (measured by the telemetry hook in R30). MCP responses honor `token_budget` in 100% of test cases.
- **Compaction safety** — Truncating any `SKILL.md` to its first 5,000 tokens still produces a correct (if rougher) output on the smoke-test fixture for that skill.
- **Codex parity** — `kitty:review` and `kitty:work` execute under Codex with real subagent spawning (verified by `[agents] max_threads` enforcement in logs), not inline-only.
- **Generator integrity** — `scripts/generate_agents.py` and the manifest generator (R20, R24) run clean in CI; deleting a generated file and re-running restores it byte-for-byte.
- **Agent specialization** — Every agent's `tools` field is minimum-viable; review-agent costs on Sonnet are ≤25% of inherit-Opus costs at parity quality (measured by manual review).
- **Observability** — `kitty.telemetry.json` lines exist for every skill run; the validator (R28) and tool-reference generator (R29) gate CI.
- **No regression** — All existing tests pass, including `test_workflow_skills_require_memory_preflight`.

## Scope Boundaries

**In scope:**
- All harness layers: SKILL.md prompts, agent .md/.toml files, MCP server tool signatures and response shapes, plugin manifests, generators, validators, hooks, smoke tests.
- The memory database (extending with `agent_handoffs`).
- Codex `.codex/agents/*.toml`, `.codex/config.toml`, `agents/openai.yaml` per skill.
- `AGENTS.md` restoration and synchronisation with `CLAUDE.md`.

**Out of scope:**
- New graph capabilities (hybrid retrieval, LSP, additional languages, multi-dim graph, embeddings) — owned by `2026-04-23-001-plugin-evolution`.
- Extracting skills into a separate Git submodule — owned by `2026-04-27-001-skills-submodule-repository`. R20 and R24's generators must be relocatable when that extraction happens, but the extraction itself is not this RFC.
- Upstream MCP-spec changes — we adopt June 2025 spec features; we do not propose new ones.
- Gemini and OpenCode runtime feature parity beyond keeping their existing manifests building. Codex + Claude Code are the priority runtimes per user direction.

## Key Decisions

- **V2/RFC-grade overhaul, not incremental hardening.** User-confirmed. Implies coordinated MCP signature changes + skill rewrites + agent regeneration in one campaign, not surgical edits.
- **Single source of truth for agents and manifests; generated outputs for each runtime.** User-confirmed. Trades one-time generator complexity for permanent drift safety. The `_source/` files become the contract.
- **MCP tool-signature changes are in scope.** User-confirmed. Adds `outputSchema`, `response_shape`, `token_budget`, `cursor`, `cleanable` parameters across the high-traffic tools. Existing callers using only required positional args remain compatible; new params default to current behavior.
- **Sonnet for subagents, Opus for orchestrator** — adopts Anthropic's documented reference architecture. Documented opt-out for cases that need Opus depth.
- **Compaction-aware skill design** — every skill's first 5,000 tokens carry the decision tree, tool matrix, and contract; references hold the rest. This is a hard structural constraint, not a guideline.
- **Tool-result clearing as a server-driven hint, not a skill heuristic.** Server tags `cleanable: true` on responses safe to drop; skills follow the hint deterministically. Avoids per-skill divergent rules.
- **Specialization > breadth.** The agent count stays at 9 (plus the proposed `expert-kitten-context`). Each gets sharper tool permissions, sharper output contracts, and embedded scaling rules. We do not split agents further or add a "general" agent.

## Open Questions

### Resolve before planning

- **Q-A. Generator language and location.** Python (matches `cartograph` codebase) or a runtime-neutral shell + jinja approach (lighter for the future skills-submodule extraction)? Recommendation: Python, `scripts/generate_agents.py` and `scripts/generate_manifests.py`, using `jinja2` templates under `plugins/kitty/_source/templates/`. Confirm before R20/R24 land.
- **Q-B. MCP backward compatibility.** Should `response_shape` default to `"standard"` (matching today's output) or to `"compact"` (forcing every caller to opt into the larger shape)? Default `"standard"` is safer; default `"compact"` is more aggressive about token reduction. Recommendation: `"standard"` default, `"compact"` becomes the canonical recommendation in `tool-reference.md` for skills/agents.
- **Q-C. Codex `.codex/agents/` location relative to the plugin.** Codex CLI looks for project-scoped agents in `.codex/agents/` at the *repo root*. Plugins shipping their own `.codex/agents/` may or may not be auto-discovered — needs verification. Fallback: ship an installer script that copies plugin-side TOML files into the repo's `.codex/agents/` on first activation. Recommendation: spike this with a real Codex install before R19 commits to a path layout.
- **Q-D. Telemetry storage.** Local file (`.pawprints/telemetry.jsonl`)? SQLite table? Prometheus exporter? Recommendation: append-only `.jsonl`, rotated daily, with a `kitty:status` extension to query it. Cheap and inspectable.

### Deferred (resolve during implementation)

- **Q-E. Sub-skills as siblings vs. nested under `kitty/` parent.** `kitty/skills/kitty-review/` (sibling) vs. `kitty/skills/kitty/skills/review/` (nested). Claude Code's plugin layout flattens — sibling layout wins by convention. Confirm during R7 work.
- **Q-F. `expert-kitten-context` agent — always-on or conditional?** Always-on adds latency and cost on every review; conditional (gated by orchestrator-side context size) is cheaper. Recommendation: conditional, threshold = 10,000-token subgraph context. Validate in R18.
- **Q-G. Hook policy under Codex.** Codex hooks may differ in semantics from Claude Code hooks. R31 may have to ship runtime-specific hook implementations. Defer until the Codex hook docs are read end-to-end.
- **Q-H. `kitty:compact` skill vs. relying on built-in compaction.** Claude Code already has auto-compaction with a documented protocol. We may only need to add memory-write side-effects, not a full new skill. Recommendation: hooks + memory writes, no new skill, unless a gap appears.

## Suggested implementation phasing (advisory — owned by `kitty:plan`)

1. **Foundation:** R19 (source-of-truth format), R20 (agent generator), R28 (skill validator). Lands the contracts.
2. **MCP shaping:** R1, R2, R3 (output schemas, response shapes, token budgets) on `query.py` and `analysis.py` first.
3. **Skill restructure:** R7 (split skills), R10 (compaction-resilient layout), R8 (frontmatter expansion), R9 (`!command` injections).
4. **Agent specialization:** R12, R13, R14, R15 (tools, model, scaling rules, output contract). R16, R17 (consolidation, spawn map) come for free during regeneration.
5. **Codex parity:** R21–R24 (config, openai.yaml, AGENTS.md, manifests).
6. **Memory + handoff + observability:** R25, R26, R27, R30, R31, R32 — last because they depend on the prior surfaces.
7. **Optional polish:** R5 (tool consolidation), R11 (router-as-manifest), R18 (`expert-kitten-context`), R29 (autogenerated tool reference).
