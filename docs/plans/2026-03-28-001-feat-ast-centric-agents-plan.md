---
title: AST-Centric Agent Architecture
type: feat
status: complete
date: 2026-03-28
origin: docs/brainstorms/2026-03-28-001-ast-centric-agents-requirements.md
implemented_in: c2199ea
units:
  - id: 1
    title: Surface Annotation Data in Tool Responses
    state: complete
    implemented_in: c2199ea
  - id: 2
    title: Define Standard Subgraph Context Format
    state: complete
    implemented_in: c2199ea
  - id: 3
    title: Review Skill Orchestrator + Reviewer Agents
    state: complete
    implemented_in: c2199ea
  - id: 4
    title: Plan & Brainstorm Skill Orchestrators + Research Agents
    state: complete
    implemented_in: c2199ea
  - id: 5
    title: Work Skill Orchestrator + Annotator Agent
    state: complete
    implemented_in: c2199ea
  - id: 6
    title: Reference Documentation Updates
    state: complete
    implemented_in: c2199ea
---

# AST-Centric Agent Architecture — Implementation Plan

## Overview

Make Cartograph agents genuinely AST/annotation-centric by:
1. Surfacing `tags` and `role` in all MCP tool responses (server layer)
2. Making skill orchestrators the intelligence hub — they call MCP tools, build annotated subgraphs, and pass rich context to agents
3. Rewriting all 9 agents to work from pre-computed graph context instead of attempting MCP calls they cannot make

## Problem Frame

Plugin subagents cannot access MCP tools (known Claude Code platform limitation). All 9 agents reference Cartograph tools in their workflows but declare `tools: Read, Grep, Glob, Bash` — the only tools they can actually use. Annotations (summaries, tags, roles) are stored but never consumed. The fix: orchestrators pre-compute graph context via MCP tools and pass it as structured text to agents.

## Requirements Trace

| Requirement | Implementation Unit |
|-------------|-------------------|
| R1. `_summarise_node` includes tags/role | Unit 1 |
| R2. find_deps/dependents include annotation fields | Unit 1 |
| R3. All node-returning tools surface annotations | Unit 1 |
| R4. Review skill pre-computes annotated subgraph | Unit 3 |
| R5. Review skill passes subgraph context to reviewers | Unit 3 |
| R6. Review skill checks annotation_status | Unit 3 |
| R7. Plan skill pre-computes graph context | Unit 4 |
| R8. Work skill pre-computes graph context | Unit 5 |
| R9. Brainstorm skill pre-computes graph context | Unit 4 |
| R10-R14. Reviewer agents work from pre-computed context | Unit 3 |
| R15-R17. Research agents work from pre-computed context | Unit 4 |
| R18-R19. Annotator agent special handling | Unit 5 |
| R20-R21. Worker agents receive graph context | Unit 5 |
| R22. Standard subgraph context format | Unit 2 |

## Scope Boundaries

**In scope:** Server tool responses, all 9 agent .md files, 4 skill SKILL.md files, reference docs, new tests for annotation fields.

**Out of scope:** Parsing layer, storage schema, annotation generation logic, new MCP tools, new agent types.

## Context & Research

### Server Data Flow (from flow-analyzer)

Annotation data exists at every level but gets stripped at two exact points:

| Strip Point | File:Lines | What's Dropped |
|-------------|-----------|----------------|
| `_summarise_node` | `query.py:111-124` | `properties` (tags/role) |
| Inline dict comprehensions | `analysis.py:46-55, 81-89` | ALL annotation fields including `summary` |

The storage layer (`graph_store.py`) returns complete data — `_row_to_dict` deserializes `properties` JSON. The tool layer is the only place data is lost.

### Agent Tool Usage (from pattern-analyst)

| MCP Tool | Agents Referencing It | Pre-compute Strategy |
|----------|----------------------|---------------------|
| `get_file_structure` | 5 agents | Orchestrator calls for each modified/target file |
| `query_node` | 6 agents | Orchestrator calls for each modified symbol |
| `find_dependents` | 5 agents | Orchestrator calls for modified public symbols (depth 3) |
| `find_dependencies` | 6 agents | Orchestrator calls for modified symbols |
| `search` | 3 agents | Orchestrator calls with domain terms |
| `index_codebase` | 4 agents | Orchestrator calls once at start |
| `annotation_status` | 2 agents | Orchestrator calls once and includes in context |

### Blast Radius (from impact-analyst)

- **Risk: LOW** — all server changes are additive (new dict keys), all plugin changes are content-only
- No tests assert on exact key sets — adding `tags`/`role` won't break anything
- CI validates file existence, not content — safe to modify .md files freely
- Should ADD tests verifying tags/role appear after annotation

### Key Constraints

- Agent `.md` files cannot be renamed (CI checks existence)
- Output contracts (reviewer JSON schema, research text format) must be preserved
- `tools:` frontmatter stays as `Read, Grep, Glob, Bash` — this is correct given the platform limitation
- Annotator agent is unique — needs write-back path (orchestrator-mediated or general-purpose dispatch)

## Key Technical Decisions

1. **Refactor analysis.py to use `_summarise_node`** rather than duplicating fields in inline dicts — prevents drift between tools
2. **Standard subgraph context format** as a reference doc agents can link to — ensures consistency across orchestrators
3. **Annotator handled via orchestrator mediation** — annotate skill pre-fetches pending nodes, passes to annotator, annotator returns annotations as JSON, orchestrator submits them
4. **"Expected Context" section in every agent** — explicit contract between orchestrator and agent about what data is provided
5. **Preserve all output contracts** — reviewer JSON schemas and research text formats are consumed downstream

## Open Questions

### Deferred
- Graph context budget (how much subgraph data per agent before context bloat)
- Whether to add `tags`/`role` to FTS5 index for tag-based search
- Edge contract verification as a dedicated reviewer vs. shared responsibility

---

## Implementation Units

### Unit 1: Surface Annotation Data in Tool Responses

**State:** complete — implemented in c2199ea

- [ ] **Goal:** Make `tags`, `role`, `summary`, and `annotation_status` available in ALL MCP tool responses that return node data
- **Requirements:** R1, R2, R3
- **Dependencies:** None (prerequisite for all other units)
- **Files:**
  - Modify: `src/cartograph/server/tools/query.py`
  - Modify: `src/cartograph/server/tools/analysis.py`
  - Modify: `tests/test_server.py`
  - Modify: `tests/test_stdio_e2e.py`
- **Approach:**
  1. In `_summarise_node` (query.py:111-124), extract `tags` and `role` from the `properties` dict:
     ```python
     props = node.get("properties") or {}
     # ...existing fields...
     "tags": props.get("tags", []),
     "role": props.get("role", ""),
     ```
  2. In `analysis.py`, replace inline dict comprehensions (lines 46-55 and 81-89) with calls to `_summarise_node` + add `depth`. Import `_summarise_node` from `query.py` (or extract to a shared `_helpers.py` if circular import is a concern).
  3. Add `depth` to `_summarise_node` return when present (use `.get("depth")` — only set for traversal results).
- **Patterns to follow:** The existing `_summarise_node` pattern — a single function that controls the public API surface of node data.
- **Test scenarios:**
  - Happy path: After `submit_annotations`, `query_node` returns `tags` and `role` fields populated
  - Happy path: After `submit_annotations`, `find_dependents`/`find_dependencies` return `summary`, `tags`, `role` for each node
  - Happy path: `get_file_structure` returns `tags` and `role` for annotated nodes
  - Happy path: `search` returns `tags` and `role` for annotated results
  - Edge case: Unannotated nodes return `tags: []`, `role: ""`, `summary: null`
  - Edge case: Nodes with `properties` as empty dict or null
- **Verification:** `uv run pytest tests/test_server.py tests/test_stdio_e2e.py` passes. Manual check: index a fixture, annotate, then call each tool and verify tags/role appear.

---

### Unit 2: Define Standard Subgraph Context Format

**State:** complete — implemented in c2199ea

- [ ] **Goal:** Define the structured text format that orchestrators produce and agents consume, so all parties agree on the contract
- **Requirements:** R22
- **Dependencies:** Unit 1 (format must reflect enriched tool responses)
- **Files:**
  - Create: `plugins/cartograph/skills/cartograph/references/subgraph-context-format.md`
  - Modify: `plugins/cartograph/skills/cartograph/references/tool-reference.md` (update response shapes)
- **Approach:**
  Define a markdown-based context format with these sections:
  ```
  ## Annotation Status
  [annotated/pending/failed counts]

  ## Changed Nodes
  [For each: qualified_name, kind, summary, role, tags, file:line, annotation_status]

  ## Edges Between Changed Nodes
  [For each: source → target, edge_kind — highlights contracts to verify]

  ## Neighbors (1-hop)
  [Immediate callers/callees/imports of changed nodes, with summaries and roles]

  ## Transitive Dependents (blast radius)
  [From find_dependents, depth-annotated, with summaries and roles]
  [Grouped by role/tag when possible: "3 API handlers, 2 services, 1 test"]

  ## Transitive Dependencies (upstream)
  [From find_dependencies, with summaries and roles]
  ```
  Also update `tool-reference.md` to document the new `tags` and `role` fields in all tool responses.
- **Patterns to follow:** Existing `tool-reference.md` and `annotation-workflow.md` as reference doc examples.
- **Test scenarios:**
  - Happy path: Format is parseable and referenced by at least one orchestrator skill
  - Edge case: Format handles empty/missing annotation data gracefully (shows "not annotated" status)
- **Verification:** All orchestrator skills in Units 3-5 reference this format. Agent "Expected Context" sections match it.

---

### Unit 3: Review Skill Orchestrator + Reviewer Agents

**State:** complete — implemented in c2199ea

- [ ] **Goal:** The review skill pre-computes an annotated subgraph of changed symbols and passes it to reviewer agents. Reviewers work from this graph context to check relationships, not just individual nodes.
- **Requirements:** R4, R5, R6, R10, R11, R12, R13, R14
- **Dependencies:** Unit 1 (enriched tool responses), Unit 2 (context format)
- **Files:**
  - Modify: `plugins/cartograph/skills/cartograph-review/SKILL.md`
  - Modify: `plugins/cartograph/agents/cartograph-correctness-reviewer.md`
  - Modify: `plugins/cartograph/agents/cartograph-testing-reviewer.md`
  - Modify: `plugins/cartograph/agents/cartograph-impact-reviewer.md`
  - Modify: `plugins/cartograph/agents/cartograph-structure-reviewer.md`
- **Approach:**

  **Review skill changes:**
  1. After computing the diff and file list (existing Stage 1-2), add a new "Build Subgraph Context" stage:
     - Call `annotation_status()` — warn if >50% nodes are unannotated
     - For each modified file: call `get_file_structure` to get all nodes with annotations
     - For each modified symbol (identified from diff + file structure): call `query_node` to get neighbors with annotations
     - For modified public symbols: call `find_dependents(max_depth=3)` for blast radius
     - For all modified symbols: call `find_dependencies` for upstream context
     - Identify edges between changed nodes from the neighbor data
     - Format all results using the standard subgraph context format (Unit 2)
  2. Pass the formatted subgraph context block to each reviewer agent alongside the existing diff + file list + intent
  3. Instruct reviewers to check edges between changed nodes for contract consistency

  **Reviewer agent changes (all 4):**
  1. Add an "Expected Context" section listing what the orchestrator provides
  2. Rewrite workflow from tool-call steps to analysis-of-provided-data steps:
     - "From the subgraph context, identify all edges between changed nodes"
     - "For each edge, verify the contract holds (caller matches callee signature, etc.)"
     - "Use node summaries and roles to understand purpose before reading source"
  3. Keep `Read, Grep, Glob, Bash` as fallback: "If source detail is needed beyond what the graph context provides, use Read"
  4. Remove all references to calling MCP tools directly
  5. Preserve output JSON contracts exactly (reviewer name, findings array, summary)
  6. Preserve confidence calibration rules

  **Agent-specific changes:**
  - **correctness-reviewer:** Workflow emphasizes checking state flow across edges, using summaries for intent verification
  - **testing-reviewer:** Expects test-file dependents in context, checks coverage against changed symbols. Keep `testing_gaps` field
  - **impact-reviewer:** Expects depth-annotated transitive dependents, groups by role/tag for semantic blast radius. Keep `affected_dependents` field
  - **structure-reviewer:** Expects search results for similar nodes, checks naming/pattern consistency against existing conventions

- **Patterns to follow:** Current review skill stage structure (keep numbered stages). Current reviewer output JSON schema.
- **Test scenarios:**
  - Happy path: Review skill calls MCP tools and builds subgraph context before dispatching reviewers
  - Happy path: Reviewer findings reference node relationships ("A calls B, change breaks contract")
  - Happy path: Reviewer output includes annotation data in findings ("role: API handler")
  - Edge case: Review on unannotated codebase — reviewers fall back to source reading, skill warns about annotation status
  - Integration: Full review pipeline produces merged findings with relationship-aware issues
- **Verification:** Run `cartograph:review` on a test diff. Reviewers produce findings referencing graph relationships and annotation data. Output JSON matches existing schema.

---

### Unit 4: Plan & Brainstorm Skill Orchestrators + Research Agents

**State:** complete — implemented in c2199ea

- [ ] **Goal:** Plan and brainstorm skills pre-compute graph context for their scope area and pass it to research agents. Research agents analyze pre-computed context instead of attempting MCP calls.
- **Requirements:** R7, R9, R15, R16, R17
- **Dependencies:** Unit 1 (enriched tool responses), Unit 2 (context format)
- **Files:**
  - Modify: `plugins/cartograph/skills/cartograph-plan/SKILL.md`
  - Modify: `plugins/cartograph/skills/cartograph-brainstorm/SKILL.md`
  - Modify: `plugins/cartograph/agents/cartograph-researcher.md`
  - Modify: `plugins/cartograph/agents/cartograph-pattern-analyst.md`
  - Modify: `plugins/cartograph/agents/cartograph-flow-analyzer.md`
  - Modify: `plugins/cartograph/agents/cartograph-impact-analyst.md`
- **Approach:**

  **Skill orchestrator changes (plan + brainstorm):**
  1. After calling `index_codebase`, add a "Build Research Context" phase:
     - Call `annotation_status()` — include counts in context
     - Call `search` with feature-area keywords to find relevant nodes
     - Call `get_file_structure` on key files identified by search
     - Call `query_node` on important symbols from search results
     - For plan skill: call `find_dependencies` and `find_dependents` on the target area for the flow-analyzer and impact-analyst
     - Format using standard subgraph context format
  2. Pass the formatted context to each research agent alongside the feature description
  3. For plan skill: pass flow-specific context (call-edge dependencies, depth 3-4) to flow-analyzer, and impact-specific context (transitive dependents) to impact-analyst

  **Research agent changes (all 4):**
  1. Add "Expected Context" section
  2. Rewrite workflow from tool-call steps to analysis steps:
     - "From the graph context, identify the technology stack and architecture"
     - "From the node summaries and roles, classify code by domain layer"
     - "From the search results, identify existing patterns for this feature area"
  3. Remove `index_codebase` references (orchestrator handles this)
  4. Keep Read/Grep/Glob/Bash as fallback for reading source files
  5. Preserve output formats (free-form structured text sections)

  **Agent-specific changes:**
  - **researcher:** Broad context — expects file structures, node data, search results, annotation status. Uses summaries/roles for architecture understanding
  - **pattern-analyst:** Expects search results and file structures for the feature area. Step 6 ("Read actual source of 2-3 exemplar files") stays — it uses Read which is available
  - **flow-analyzer:** Expects pre-computed transitive call-edge dependencies (depth 3-4) with node data at each step. Describes chains semantically using roles
  - **impact-analyst:** Expects transitive dependents with depth annotations. Groups by role/tag for semantic blast radius

- **Patterns to follow:** Current skill phase structure. Current agent output text formats.
- **Test scenarios:**
  - Happy path: Plan skill builds research context with annotation data before dispatching agents
  - Happy path: Research agent output references summaries, roles, tags from the graph
  - Happy path: Flow-analyzer describes call chains using role labels ("API handler -> validation -> data access")
  - Edge case: Unannotated codebase — agents note limitation, fall back to structural analysis
- **Verification:** Run `cartograph:plan` on a feature request. Research agents produce findings that reference annotation data. Plan includes role/tag-based understanding.

---

### Unit 5: Work Skill Orchestrator + Annotator Agent

**State:** complete — implemented in c2199ea

- [ ] **Goal:** Work skill pre-computes graph context for each implementation unit's target files. Annotator agent is handled via orchestrator mediation (the annotate skill pre-fetches pending nodes and submits results).
- **Requirements:** R8, R18, R19, R20, R21
- **Dependencies:** Unit 1 (enriched tool responses), Unit 2 (context format)
- **Files:**
  - Modify: `plugins/cartograph/skills/cartograph-work/SKILL.md`
  - Modify: `plugins/cartograph/skills/cartograph-annotate/SKILL.md`
  - Modify: `plugins/cartograph/agents/cartograph-annotator.md`
- **Approach:**

  **Work skill changes:**
  1. In the worker dispatch phase, before spawning each worker subagent:
     - Call `get_file_structure` on every file in the unit's Files section
     - Call `query_node` on key symbols in those files
     - Format as subgraph context and include in the worker prompt
  2. Worker instructions change from "Start by calling get_file_structure" to "Review the graph context provided, then implement"
  3. Workers use summaries/roles to understand file purpose before modifying

  **Annotate skill changes:**
  The annotate skill already runs in the main conversation with MCP access. Make it the mediator:
  1. Skill calls `get_pending_annotations(batch_size=N)` to get pending nodes
  2. Formats pending nodes as context for the annotator agent
  3. Dispatches annotator agent with the pending node data
  4. Annotator analyzes each node (using Read to check source if needed) and returns annotations as structured JSON
  5. Skill receives the JSON and calls `submit_annotations` to write back to the graph
  6. Repeat until no more pending nodes

  **Annotator agent changes:**
  1. Add "Expected Context" section: receives pending node batch with source code, metadata, neighbor context
  2. Remove `get_pending_annotations` and `submit_annotations` from workflow
  3. Output contract changes: returns a JSON array of annotation results instead of calling submit directly:
     ```json
     [{"qualified_name": "...", "summary": "...", "tags": [...], "role": "...", "failed": false}]
     ```
  4. Keep annotation guidelines, seed taxonomy reference, quality bar

- **Patterns to follow:** Current work skill dispatch template. Current annotate skill batch loop.
- **Test scenarios:**
  - Happy path: Work skill provides graph context to workers before they implement
  - Happy path: Annotate skill mediates between pending nodes and annotator agent
  - Happy path: Annotator returns valid annotation JSON that the skill submits successfully
  - Edge case: Annotator fails on some nodes — returns `failed: true`, skill handles gracefully
- **Verification:** Run `cartograph:work` on a plan unit — workers receive graph context. Run `cartograph:annotate` — annotations are written to the graph via orchestrator mediation.

---

### Unit 6: Reference Documentation Updates

**State:** complete — implemented in c2199ea

- [ ] **Goal:** Update all reference documentation to reflect the new architecture — enriched tool responses, orchestrator-mediated context, agent contracts
- **Requirements:** Supports all requirements (documentation)
- **Dependencies:** Units 1-5
- **Files:**
  - Modify: `plugins/cartograph/skills/cartograph/references/tool-reference.md`
  - Modify: `plugins/cartograph/skills/cartograph/references/annotation-workflow.md`
  - Modify: `plugins/cartograph/skills/cartograph/SKILL.md` (router skill — if it references agent capabilities)
- **Approach:**
  1. `tool-reference.md`: Update response shapes for `query_node`, `search`, `get_file_structure`, `find_dependencies`, `find_dependents` to include `tags`, `role` fields. Document the `depth` field in dependency results.
  2. `annotation-workflow.md`: Add a "Consuming Annotations" section explaining that orchestrator skills pre-compute annotated subgraphs and agents receive annotation data as text context. Document the orchestrator-mediated annotator pattern.
  3. Router skill: Update any references to agent capabilities to reflect the pre-computed context architecture.
- **Patterns to follow:** Existing reference doc style.
- **Test scenarios:**
  - Happy path: tool-reference.md accurately reflects actual tool response shapes
  - Happy path: annotation-workflow.md describes the full lifecycle including consumption
- **Verification:** Compare documented response shapes against actual tool output. Verify all agents' "Expected Context" sections reference the subgraph context format.

---

## System-Wide Impact

- **Additive server changes only** — no existing tool behavior is removed, only enriched
- **Agent .md files are content-only changes** — no renames, no deletions, CI passes
- **Skill SKILL.md files are content-only changes** — structure preserved
- **Annotation data becomes a first-class citizen** — written by annotator, stored in graph, surfaced by tools, consumed by agents via orchestrators
- **Orchestrators become the intelligence hub** — clean separation between context gathering (orchestrator) and analysis (agent)

## Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| Pre-computed context too large for agent context window | Orchestrators should filter to relevant nodes only; defer "context budget" limits |
| Orchestrator MCP calls add latency before agent dispatch | Calls are parallelizable; total time still less than 4+ agents each making separate calls |
| Annotation data often missing (unannotated codebase) | All agents fall back gracefully; annotation_status check warns upfront |
| Platform fixes plugin MCP access later | Architecture is forward-compatible — agents can gain ad-hoc MCP access as supplement |
| `_summarise_node` import in analysis.py could cause circular imports | Extract to `src/cartograph/server/tools/_helpers.py` if needed |

## Sources & References

- [Official docs: plugin subagent restrictions](https://code.claude.com/docs/en/sub-agents) — `mcpServers` unsupported for plugin agents
- [#13605](https://github.com/anthropics/claude-code/issues/13605), [#21560](https://github.com/anthropics/claude-code/issues/21560), [#25200](https://github.com/anthropics/claude-code/issues/25200) — MCP tools unavailable to plugin subagents
- Requirements doc: `docs/brainstorms/2026-03-28-001-ast-centric-agents-requirements.md`
