---
name: cartograph:plan
description: >
  Create technical implementation plans using Cartograph research agent swarms for
  deep codebase understanding. Use when the user says "plan this", "create a plan",
  "how should we build this", or after brainstorming to turn requirements into an
  actionable plan. Dispatches 3-4 research agents in parallel for comprehensive analysis.
argument-hint: "[feature description or requirements doc path]"
---

# Cartograph: Plan

Define **HOW** to build through Cartograph-powered research and structured planning.
Produces an implementation plan that feeds into `cartograph:work`.

## Interaction Method

Use the platform's blocking question tool when available. Ask one question at a time.

## Workflow

### Phase 0: Source & Resume

1. Check `docs/plans/` for existing plans matching the topic — offer to resume if found
2. Check `docs/brainstorms/` for requirements documents — use as origin if found
3. If no origin document, assess whether the request is clear enough for direct planning
4. Classify plan depth: **Lightweight** (2-4 units), **Standard** (3-6), **Deep** (4-8)

### Phase 1: Index & Build Research Context

Call `index_codebase(full=false)` to ensure the graph is fresh.

**Build the subgraph context that research agents will consume:**

1. **Annotation status** — Call `annotation_status()`. Record total nodes, annotated count, and coverage percentage.

2. **Search for target nodes** — Call `search` with 2-4 feature-area keywords extracted from the feature description or requirements. Collect the matching qualified names, file paths, summaries, tags, and roles.

3. **File structures** — Call `get_file_structure` on the top 3-5 files identified by search results. Capture the full node listings with their kinds, summaries, tags, and roles.

4. **Key symbol details** — Call `query_node` on the 3-5 most important symbols from search results (classes, entry points, core functions). Capture their metadata, neighbors, and edge kinds.

5. **Dependency context** — Call `find_dependencies` on the primary target symbols (depth 2-3) to understand what the target area relies on. Call `find_dependents` on the same symbols (depth 2-3) to understand what relies on the target area.

6. **Flow-specific context** — Call `find_dependencies(edge_kinds=["calls"])` on entry points at depth 3-4 to pre-compute the call chains the flow-analyzer needs.

7. **Impact-specific context** — Call `find_dependents` on the symbols most likely to be changed, at depth 3-4, to pre-compute the transitive blast radius the impact-analyst needs.

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

### Phase 1b: Research Swarm

Dispatch these agents in **parallel**, passing each the feature description, origin requirements, AND the formatted subgraph context:

- **`cartograph-researcher`** — Pass: full subgraph context (annotation status, target nodes, file structures, symbol details, dependencies)
- **`cartograph-pattern-analyst`** — Pass: search results, file structures, and symbol details from the subgraph context
- **`cartograph-flow-analyzer`** — Pass: call-edge dependencies section specifically (depth 3-4 call chains with node data and roles)
- **`cartograph-impact-analyst`** — Pass: blast radius section specifically (transitive dependents with depth annotations, roles, and tags)

Consolidate findings into:
- Relevant patterns and file paths
- Dependency chains and blast radius
- Technology constraints
- Existing conventions to follow

### Phase 2: Resolve Questions

Build question list from origin document + research gaps.

For each question, decide:
- **Resolve now** — answer is knowable from Cartograph research or user input
- **Defer to implementation** — depends on runtime behavior or code changes

Ask user only when the answer materially affects architecture, scope, or risk.

**Pipeline mode:** Resolve questions automatically from research findings.

### Phase 3: Structure the Plan

Break work into implementation units. Each unit:
- **Goal** — what it accomplishes
- **Requirements** — which R1, R2, etc. it advances
- **Dependencies** — what must exist first
- **Files** — exact paths to create/modify/test
- **Approach** — key design decisions
- **Patterns to follow** — from `cartograph-pattern-analyst` findings
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
- Dispatch targeted research agents to fill gaps
- Update the plan with stronger rationale

**Gate:** Skip for Lightweight plans unless high-risk. Always run for Standard/Deep.

### Phase 6: Handoff

**Pipeline mode:** Return plan file path. Skip interactive menu.

**Interactive mode:** Present options:
1. Run `cartograph:review` on the plan (recommended for Deep plans)
2. Start `cartograph:work` to implement
3. Open plan in editor
