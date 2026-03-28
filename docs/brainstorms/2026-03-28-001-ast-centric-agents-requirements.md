# AST-Centric Agent Architecture — Requirements

## Problem Frame

The Cartograph plugin has a powerful AST graph database with annotation support (summaries, tags, roles), but agents and skills don't actually use it. All 9 agents declare `tools: Read, Grep, Glob, Bash` in their frontmatter — none have access to Cartograph MCP tools. Reviewers check nodes independently instead of checking their relationships through the graph. Annotations are write-only: the system stores summaries, tags, and roles, but no agent reads them. The result is that the plugin's core differentiator — structural, relationship-aware intelligence — is aspirational, not functional.

## Platform Constraint: MCP Tools in Plugin Subagents

**Critical finding (verified online + empirically in this session):**

Plugin-defined subagents **cannot access MCP tools** regardless of frontmatter configuration. This is a known, unresolved platform limitation in Claude Code (v2.1.86):

- `tools:` is an allowlist — listing `Read, Grep, Glob, Bash` blocks MCP tools
- Removing `tools:` entirely does NOT fix it — plugin agents still can't access MCP tools
- `disallowedTools:` does NOT fix it — plugin agents never receive MCP tools to begin with
- `mcpServers` frontmatter is **explicitly unsupported** for plugin agents (per official docs)
- Empirically confirmed: both research agents dispatched in this session made **0 MCP tool calls** despite workflow instructions mandating them — they fell back to `Read` and `Bash`

**What DOES work:**
- The **main conversation** (where skills run) has full MCP tool access
- **Built-in agents** (`general-purpose`, `Explore`, `Plan`) can access MCP tools
- Skills with `context: fork` + `agent: general-purpose` get MCP access via the built-in agent

**References:**
- [Official docs: plugin subagent restrictions](https://code.claude.com/docs/en/sub-agents)
- [#13605](https://github.com/anthropics/claude-code/issues/13605) — Custom plugin subagents cannot access MCP tools (closed, not fixed)
- [#21560](https://github.com/anthropics/claude-code/issues/21560) — Plugin-defined subagents cannot access MCP tools (open)
- [#25200](https://github.com/anthropics/claude-code/issues/25200) — Custom agents cannot use deferred MCP tools (open)
- [#23374](https://github.com/anthropics/claude-code/issues/23374) — Allow subagents to access MCP tools (closed as duplicate)
- [#19964](https://github.com/anthropics/claude-code/issues/19964) — Contradictory MCP tool documentation (closed, not fixed)

## Viable Workaround Options

### Option A: Orchestrator Pre-Fetches, Agents Consume Text (Recommended)

The skill orchestrator runs in the main conversation and **has full MCP access**. It calls all Cartograph tools, builds a rich annotated subgraph, and passes it as structured text context to agents. Agents work from this pre-computed context using only `Read, Grep, Glob, Bash`.

**How it works for review:**
1. Review skill calls `index_codebase`, `query_node`, `find_dependents`, `find_dependencies` on all changed symbols
2. Builds an annotated subgraph with summaries, tags, roles, edges, and neighbor context
3. Passes this as a structured text block to each reviewer agent alongside the diff
4. Reviewers analyze relationships from the pre-computed graph data without needing MCP tools

**Pros:**
- Works today with zero platform dependency
- Actually **better** than agents calling MCP tools individually — orchestrator makes one holistic pass, all agents share the same rich context
- Reduces redundant MCP calls (1 orchestrator pass vs. 4+ agents each calling tools)
- Agents stay focused on their review domain instead of spending turns on graph traversal
- Graph context is curated — orchestrator can be smart about what to include

**Cons:**
- Agents can't do ad-hoc graph queries during review (must fall back to Read/Grep)
- Orchestrator must anticipate all context agents might need
- More context passed to each agent (mitigated by smart filtering)

### Option B: Dispatch as `general-purpose` with Custom Prompts

Instead of custom plugin agents, dispatch all agents as the built-in `general-purpose` type with the agent's full prompt injected inline.

**Pros:**
- `general-purpose` CAN access MCP tools (confirmed)
- Agents get direct graph access for ad-hoc queries

**Cons:**
- Loses agent identity (name, color, description) in UI
- Loses agent `.md` file as a reusable, versionable artifact
- Reports of inconsistent MCP access even with `general-purpose` ([#14496](https://github.com/anthropics/claude-code/issues/14496))
- Each agent redundantly discovers graph context instead of sharing a single pre-computed view
- More total MCP calls = slower reviews

### Option C: Hybrid — Orchestrator Pre-Fetches + `general-purpose` for Deep Dives

Orchestrator pre-computes the annotated subgraph (Option A), but dispatches agents as `general-purpose` so they CAN make ad-hoc MCP calls for deeper investigation.

**Pros:**
- Best of both worlds — pre-computed context for efficiency, direct MCP access for edge cases
- Agents can follow up on suspicious findings with targeted graph queries

**Cons:**
- Most complex to implement
- Still subject to `general-purpose` MCP access inconsistencies
- Loses agent identity benefits

### Option D: Wait for Platform Fix

Design the ideal architecture (agents with direct MCP access) and wait for Anthropic to fix plugin subagent MCP access.

**Pros:**
- Cleanest long-term architecture
- No workarounds to maintain

**Cons:**
- No timeline from Anthropic — issue has been open since Dec 2025
- Plugin remains non-functional in the meantime

## Recommendation: Option A

**Option A is the strongest choice** because:

1. **It works today** — no platform dependency, no waiting
2. **It's actually architecturally superior** — a single orchestrator pass that builds a holistic view and shares it with all agents produces more consistent, relationship-aware reviews than 4 agents independently querying the graph
3. **It makes the skill orchestrators the intelligence hub** — they become the place where AST/annotation context is gathered, curated, and distributed, which is a clean separation of concerns (orchestrators gather context, agents analyze it)
4. **It's forward-compatible** — if/when Anthropic fixes plugin MCP access, agents can be upgraded to make ad-hoc queries while still receiving pre-computed context from the orchestrator

## Codebase Context

### Server Layer (MCP Tools)
- **9 MCP tools** available: `index_codebase`, `query_node`, `find_dependencies`, `find_dependents`, `search`, `get_file_structure`, `annotation_status`, `get_pending_annotations`, `submit_annotations`
- **`_summarise_node`** (`src/cartograph/server/tools/query.py:111-124`) returns `summary` and `annotation_status` but omits `tags` and `role`
- **`find_dependencies`/`find_dependents`** (`src/cartograph/server/tools/analysis.py:44-55, 79-89`) strip all annotation fields — return only `id, kind, name, qualified_name, file_path, depth`
- **Graph DB schema** stores `summary`, `annotation_status`, and `properties` (JSON with `tags` + `role`) per node
- **FTS5 index** covers `name`, `qualified_name`, `summary` — semantic search works after annotation

### Agent Layer (Plugin)
- **All 9 agents** declare `tools: Read, Grep, Glob, Bash` — zero have Cartograph MCP tools (and cannot get them due to platform limitation)
- **Agent workflows** reference Cartograph tools by name but agents cannot execute them
- **No agent** checks `annotation_status`, reads summaries/tags/roles, or queries relationships between changed nodes
- **Review skill** (`cartograph-review/SKILL.md`) calls `index_codebase` at orchestrator level but passes only raw diff + file list to reviewers — no graph context

### Key Anti-Patterns
1. Aspirational instructions with no tool access (all 9 agents)
2. Annotations are write-only in practice (no consumer)
3. Reviewers work from diff alone, checking nodes independently
4. No relationship-aware review (no edge checking between changed nodes)
5. Dependency results strip annotation data

## Requirements

### Server / Data Pipeline

- R1. `_summarise_node` must include `tags` and `role` from `properties` JSON in every tool response
- R2. `find_dependencies` and `find_dependents` must include `summary`, `tags`, `role`, and `annotation_status` in their node results
- R3. All tool responses that return node data must surface the full annotation payload so orchestrators can build rich context for agents

### Skill Orchestrators (the intelligence hub)

- R4. The review skill must call Cartograph MCP tools to pre-compute the annotated subgraph of changed symbols — `query_node` on each changed symbol to collect summaries, roles, tags, and neighbor edges; `find_dependents` for blast radius; `find_dependencies` for upstream context
- R5. The review skill must pass this subgraph context (not just raw diff + file list) to each reviewer agent as structured text
- R6. The review skill should check `annotation_status` and warn (or trigger a quick annotation pass) if changed files have many unannotated nodes
- R7. The plan skill must pre-compute graph context for the feature area and pass it to research agents
- R8. The work skill must pre-compute graph context for each implementation unit's target files and pass it to worker agents
- R9. The brainstorm skill must pre-compute relevant architecture/pattern context from the graph for research agents

### Reviewer Agents (correctness, testing, impact, structure)

- R10. Reviewer agents must be rewritten to work from pre-computed graph context (received as structured text from the orchestrator) rather than attempting MCP tool calls they cannot make
- R11. Reviewer workflows must start from the subgraph context: read node summaries, understand roles, check relationships between changed nodes, then review the diff
- R12. Reviewers must check edges between changed nodes in the pre-computed subgraph — if node A calls/imports/inherits node B and both changed, verify the contract still holds
- R13. Reviewers must consume annotation data from the subgraph: use `summary` and `role` to understand node purpose before assessing correctness
- R14. Impact reviewer must use the pre-computed `find_dependents` results (with full annotation context) to assess blast radius semantically (e.g., "3 API handlers, 2 service classes affected")

### Research & Analysis Agents (researcher, pattern-analyst, flow-analyzer, impact-analyst)

- R15. Research agents must be rewritten to work from pre-computed graph context passed by skill orchestrators
- R16. Research agents should use annotation data (summaries, tags, roles) from the pre-computed context to classify and understand code by domain
- R17. `flow-analyzer` must use edge traversal data from the pre-computed context to describe call chains semantically (e.g., "API handler -> validation layer -> data access" using roles)

### Annotator Agent

- R18. Annotator agent is the ONE exception — it needs `get_pending_annotations` and `submit_annotations` MCP tools. Since these are write operations, the annotator should be dispatched as `general-purpose` type OR the annotate skill should handle MCP calls and pass pending nodes as text
- R19. Annotator should use `annotation_status` (via orchestrator) to prioritize unannotated nodes efficiently

### Worker Agents (cartograph-work)

- R20. Worker agents must receive pre-computed graph context from the work skill orchestrator — `get_file_structure` + `query_node` results with annotation data for their target files
- R21. Workers must use annotation summaries/roles from the pre-computed context to understand the purpose of files they're modifying

### Subgraph Context Format

- R22. Define a standard structured text format for the pre-computed subgraph context that all orchestrators produce and all agents consume. Must include:
  - Changed nodes with summaries, roles, tags, annotation status
  - Edges between changed nodes (kind, source, target)
  - Immediate neighbors of changed nodes (1-hop) with summaries
  - Transitive dependents (from `find_dependents`) with summaries and roles
  - Transitive dependencies (from `find_dependencies`) with summaries and roles

## Success Criteria

- SC1. Running `cartograph:review` on a diff produces findings that reference node relationships (e.g., "Function A calls B — change to B's signature is inconsistent with A's call site")
- SC2. Reviewer output references annotation data (summaries, roles) when available, demonstrating they received and used graph context
- SC3. `find_dependents`/`find_dependencies` responses include `summary`, `tags`, `role` for each node
- SC4. The review orchestrator pre-computes and passes subgraph context (not just raw diff) to reviewer agents
- SC5. Annotation data flows end-to-end: annotator writes -> graph stores -> tools surface -> orchestrators query -> agents consume
- SC6. All skill orchestrators (review, plan, work, brainstorm) call Cartograph MCP tools to build context before dispatching agents

## Scope Boundaries

### In scope
- Server-side changes to surface `tags`, `role` in all node-returning tools
- All 9 agent `.md` files rewritten to work from pre-computed graph context (no MCP tool calls)
- All skill orchestrators (review, plan, work, brainstorm) rewritten to pre-compute annotated subgraph via MCP tools
- Standard subgraph context format definition
- Annotator agent special-cased (dispatched as `general-purpose` or orchestrator-mediated)

### Out of scope
- New MCP tools (we use the existing 9)
- Changes to the AST parsing layer (`src/cartograph/parsing/`)
- Changes to the annotation generation logic (what summaries/tags/roles contain)
- Changes to the storage schema (schema already stores everything needed)
- New agent types or new skills
- UI/CLI changes
- Fixing the Claude Code platform limitation (upstream issue)

## Key Decisions

- **Orchestrator-mediated architecture (Option A)**: Skill orchestrators are the intelligence hub — they call MCP tools, build annotated subgraphs, and pass rich context to agents. This works around the platform limitation and is architecturally superior (single holistic pass, shared context, clean separation of concerns)
- **Both layers together**: Fixing server data pipeline AND agent/skill instructions in one effort ensures annotations are surfaced and consumed end-to-end
- **All 9 agents**: Every agent is rewritten to consume pre-computed graph context
- **Edge-based review + subgraph context**: The orchestrator pre-computes the annotated subgraph AND reviewers verify contracts along edges between changed nodes
- **Annotations as primary context**: Agents should prefer annotation data from the subgraph over reading source files, falling back to source only for unannotated code or when line-level detail is needed
- **Forward-compatible**: If Anthropic fixes plugin MCP access, agents can be upgraded to make ad-hoc queries while still receiving pre-computed context

## Open Questions

### Resolve Before Planning
- (All blocking questions resolved)

### Deferred
- Should the review skill auto-trigger annotation for unannotated changed files, or just warn? (R6 says warn — could be upgraded later)
- Should there be a "graph context budget" limiting how much subgraph data is passed to agents to avoid context window bloat?
- Should edge contract verification be a dedicated reviewer agent rather than a shared responsibility?
- When Anthropic fixes plugin MCP access, should agents get direct MCP access as a supplement to orchestrator-provided context, or should the orchestrator-mediated pattern be kept as the primary?
