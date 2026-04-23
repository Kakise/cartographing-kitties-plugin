---
name: kitty:plan
description: >
  Create technical implementation plans using Cartographing Kittens research agent swarms for
  deep codebase understanding. Use when the user says "plan this", "create a plan",
  "how should we build this", or after brainstorming to turn requirements into an
  actionable plan. Uses inline-first research and optional delegation for comprehensive analysis.
argument-hint: "[feature description or requirements doc path]"
---

# Cartographing Kittens: Plan

Define **HOW** to build through Cartographing Kittens-powered research and structured planning.
Produces an implementation plan that feeds into `kitty:work`.

## Runtime Posture

This workflow is **inline-first**. The orchestrator gathers the research context and can produce
the plan end-to-end without delegation. If the active runtime supports delegation cleanly, the
preserved framework subagents may be used as an optimization rather than a hard dependency.

## Workflow

### Phase 0: Source & Resume

1. Check `docs/plans/` for existing plans matching the topic — offer to resume if found
2. Check `docs/brainstorms/` for requirements documents — use as origin if found
3. If no origin document, assess whether the request is clear enough for direct planning
4. Classify plan depth: **Lightweight** (2-4 units), **Standard** (3-6), **Deep** (4-8)

### Phase 1: Index & Build Research Context

Call `index_codebase(full=false)` to ensure the graph is fresh.

Build the subgraph context that the orchestrator and any optional research agents will consume:

1. **Annotation status** — Call `annotation_status()`. Record total nodes, annotated count, and coverage percentage.

2. **Search for target nodes** — Call `search` with 2-4 feature-area keywords extracted from the feature description or requirements. Collect the matching qualified names, file paths, summaries, tags, and roles.

3. **Context summary** — Call `get_context_summary(file_paths=[top 3-5 files from search])` for a token-efficient overview of file structures, node listings, and key metadata. This replaces N x `get_file_structure` calls.

4. **Key symbol details** — Call `batch_query_nodes(names=[3-5 most important symbols], include_neighbors=true)` for detailed info on multiple symbols at once. This replaces N x `query_node` calls.

5. **Importance ranking** — Call `rank_nodes(scope=target_files, limit=10)` to identify the most structurally important symbols in the target area. Include importance scores in the context passed to research agents.

6. **Dependency context** — Call `find_dependencies` on the primary target symbols (depth 2-3) to understand what the target area relies on. Call `find_dependents` on the same symbols (depth 2-3) to understand what relies on the target area.

7. **Flow-specific context** — Call `find_dependencies(edge_kinds=["calls"])` on entry points at depth 3-4 to pre-compute the call chains the flow-analyzer needs.

8. **Impact-specific context** — Call `find_dependents` on the symbols most likely to be changed, at depth 3-4, to pre-compute the transitive blast radius the impact-analyst needs.

**Format the context as structured text using this template:**

```
## Subgraph Context

### Annotation Status
- Total nodes: N
- Annotated: N (X%)
- Pending: N

### Target Nodes (from search)
- `qualified::name` — kind: X, role: Y, tags: [a, b], summary: "..."
  File: path/to/file.py
- ...

### File Structures
#### path/to/file.py
- `module::Class` (class) — role: Y, summary: "..."
  - `module::Class::method` (method) — role: Y, summary: "..."
- ...

### Key Symbol Details
#### `qualified::name`
- Kind: X, Role: Y, Tags: [a, b]
- Summary: "..."
- Neighbors:
  - calls -> `other::symbol` (role: Z)
  - imports -> `another::module` (role: W)
  - inherits -> `base::Class` (role: V)

### Importance Ranking (from rank_nodes)
| Qualified Name | Score | Kind | Role |
|---|---|---|---|
| critical::symbol | 0.95 | class | core |
| important::helper | 0.72 | function | utility |

### Transitive Dependencies (what target area depends on)
- Depth 1: `dep::symbol` (kind, role)
- Depth 2: `dep::dep::symbol` (kind, role)
- ...

### Transitive Dependents (what depends on target area)
- Depth 1: `consumer::symbol` (kind, role)
- Depth 2: `consumer::consumer::symbol` (kind, role)
- ...

### Call-Edge Dependencies (for flow analysis, depth 3-4)
- `entry_point` -> `called_func` -> `deeper_func` -> `leaf_func`
  Roles: handler -> validator -> data_access -> storage

### Blast Radius (for impact analysis, depth 3-4)
- `target_symbol` depended on by:
  - Depth 1: `direct_consumer` (role, tags)
  - Depth 2: `transitive_consumer` (role, tags)
  - Depth 3: `far_consumer` (role, tags)
```

### Phase 1b: Research Synthesis

Optional delegation path:

If the runtime supports delegation cleanly, the orchestrator may dispatch these framework agents
in parallel, passing each the feature description, origin requirements, and the formatted subgraph context:

- **`librarian-kitten-researcher`** — Pass: full subgraph context (annotation status, target nodes, file structures, symbol details, dependencies)
- **`librarian-kitten-pattern`** — Pass: search results, file structures, and symbol details from the subgraph context
- **`librarian-kitten-flow`** — Pass: call-edge dependencies section specifically (depth 3-4 call chains with node data and roles)
- **`librarian-kitten-impact`** — Pass: blast radius section specifically (transitive dependents with depth annotations, roles, and tags)

Whether delegated or done inline, consolidate findings into:
- Relevant patterns and file paths
- Dependency chains and blast radius
- Technology constraints
- Existing conventions to follow

### Phase 2: Resolve Questions

Build question list from origin document + research gaps.

For each question, decide:
- **Resolve now** — answer is knowable from Cartographing Kittens research or user input
- **Defer to implementation** — depends on runtime behavior or code changes

Ask the user only when the answer materially affects architecture, scope, or risk.

**Pipeline mode:** Resolve questions automatically from research findings.

### Phase 3: Structure the Plan

Break work into implementation units. Each unit:
- **Goal** — what it accomplishes
- **Requirements** — which R1, R2, etc. it advances
- **Dependencies** — what must exist first
- **Files** — exact paths to create/modify/test
- **Approach** — key design decisions
- **Patterns to follow** — from `librarian-kitten-pattern` findings
- **Test scenarios** — specific input -> expected outcome for each category:
  - Happy path (always)
  - Edge cases (when meaningful boundaries exist)
  - Error paths (when failure modes exist)
  - Integration (when crossing layers)
- **Verification** — how to know the unit is complete

### Phase 4: Write Plan

Write to `docs/plans/YYYY-MM-DD-NNN-<type>-<name>-plan.md`.

Create `docs/plans/` if needed. Use the standard plan template:

```yaml
---
title: [Plan Title]
type: feat|fix|refactor
status: active
date: YYYY-MM-DD
origin: docs/brainstorms/...-requirements.md  # if applicable
---
```

Sections: Overview, Problem Frame, Requirements Trace, Scope Boundaries,
Context & Research, Key Technical Decisions, Open Questions,
Implementation Units (with checkbox syntax), System-Wide Impact,
Risks & Dependencies, Sources & References.

### Phase 5: Confidence Check

Automatically evaluate whether the plan needs strengthening:
- Score each section for confidence gaps
- Select top 2-3 weak sections
- Dispatch targeted research agents to fill gaps when delegation is available; otherwise deepen the analysis inline
- Update the plan with stronger rationale

**Gate:** Skip for Lightweight plans unless high-risk. Always run for Standard/Deep.

### Phase 6: Handoff

**Pipeline mode:** Return plan file path. Skip interactive menu.

**Interactive mode:** Present options:
1. Run `kitty:review` on the plan (recommended for Deep plans)
2. Start `kitty:work` to implement
3. Open plan in editor

## Contract

- Must work without subagents.
- May use preserved framework subagents when the runtime supports it.
- Must not depend on a blocking-question tool or a plugin-backed agent registry.
