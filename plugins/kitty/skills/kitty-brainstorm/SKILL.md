---
name: kitty:brainstorm
description: >
  Explore requirements and approaches through Cartographing Kittens-powered codebase understanding.
  Use when starting a new feature, exploring what to build, gathering requirements,
  or when the user says "let's brainstorm", "what should we build", "help me think through".
  Uses inline-first research and optional delegation when the runtime supports it cleanly.
argument-hint: "[feature or problem description]"
---

# Cartographing Kittens: Brainstorm

Explore **WHAT** to build through dialogue and Cartographing Kittens-powered codebase analysis.
Produces a requirements document that feeds into `kitty:plan`.

## Runtime Posture

This workflow is **inline-first**. The orchestrator gathers graph context and can complete the
brainstorm without delegating. If the active runtime supports delegation cleanly, the preserved
framework subagents may be used as an optimization, not as a requirement.

## Workflow

### Phase 1: Index & Understand

1. Call `index_codebase(full=false)` to ensure the graph is fresh
2. If `$ARGUMENTS` is provided, use it as the feature description
3. If no arguments, ask: "What problem are you trying to solve or what feature are you considering?"

### Phase 2: Research Context

Build the subgraph context before any optional delegation:

1. **Annotation status** — Call `annotation_status()`. Record total nodes, annotated count, and coverage percentage.

2. **Search for relevant nodes** — Call `search` with 2-4 feature-area keywords extracted from the feature description. Collect matching qualified names, file paths, summaries, tags, and roles.

3. **File structures** — Call `get_file_structure` on the top 3-5 files identified by search results. Capture node listings with kinds, summaries, tags, and roles.

4. **Key symbol details** — Call `query_node` on the 3-5 most important symbols from search results (classes, entry points, core functions). Capture their metadata and neighbors.

5. **Dependency context** — Call `find_dependencies(name=target, max_depth=2)` for each key symbol. Understand what the feature area depends on (upstream constraints).

6. **Dependent context** — Call `find_dependents(name=target, max_depth=2)` for each key symbol. Understand who depends on the feature area (scope implications — changes here ripple outward).

**Format the context as structured text:**

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

### Edges Between Target Nodes
| Source | Target | Edge Kind |
|---|---|---|
| module::func_a | module::func_b | calls |

### Dependencies (what target area depends on)
#### `qualified::name`
- Depth 1: `dep::symbol` (kind, role)
- Depth 2: `dep::dep::symbol` (kind, role)

### Dependents (what depends on target area)
#### `qualified::name`
- Depth 1: `consumer::symbol` (kind, role)
- Depth 2: `consumer::consumer::symbol` (kind, role)
```

Optional delegation path:

If the runtime supports delegation cleanly, the orchestrator may dispatch these framework agents
in parallel, passing each the feature description and the formatted subgraph context:

- **`librarian-kitten-researcher`** — Pass: full subgraph context (annotation status, target nodes, file structures, symbol details, dependencies, dependents, edges). Scope: architecture, technology stack, module organization
- **`librarian-kitten-pattern`** — Pass: search results, file structures, and dependency/dependent context from the subgraph. Scope: existing patterns relevant to the feature area

Otherwise, the orchestrator synthesizes the same findings inline:
- technology stack
- relevant patterns
- key files
- existing conventions

### Phase 3: Adaptive Questioning

Use research findings to ask targeted questions, one at a time when interaction is needed:

1. **Problem clarity** — "Based on the codebase structure, it looks like [finding]. Is the problem about [X] or [Y]?"
2. **Scope boundaries** — "Should this include [related area found by research], or is that out of scope?"
3. **Success criteria** — "How will we know this is working? What should users be able to do?"
4. **Constraints** — Surface any constraints found by research (e.g., "The current architecture uses [pattern]. Should we follow it or propose something different?")

Stop questioning when:
- Problem is clear
- Scope is bounded
- Success criteria are defined
- 3-5 questions have been asked (don't over-question)

**Pipeline mode:** If invoked from `kitty:lfg` or another orchestrator, skip interactive questions. Infer requirements from the feature description and research findings.

### Phase 4: Write Requirements

Create the requirements document at:
`docs/brainstorms/YYYY-MM-DD-NNN-<topic>-requirements.md`

Create `docs/brainstorms/` if it doesn't exist. Check existing files for today's date to determine sequence number.

Template:
```
# [Feature Title] — Requirements

## Problem Frame
[What problem this solves and for whom]

## Codebase Context
[Key findings from Cartographing Kittens research — relevant patterns, architecture, existing code]

## Requirements
- R1. [Specific, testable requirement]
- R2. [Specific, testable requirement]

## Success Criteria
- [Observable outcome that proves requirements are met]

## Scope Boundaries
- In scope: [explicit inclusions]
- Out of scope: [explicit exclusions]

## Key Decisions
- [Decision]: [Rationale]

## Open Questions
### Resolve Before Planning
- [Blocking question]

### Deferred
- [Non-blocking question]
```

### Phase 5: Handoff

**Pipeline mode:** Return the requirements file path and continue.

**Interactive mode:** Present options:
1. Start `kitty:plan` with this requirements doc
2. Open requirements in editor for review
3. Continue refining requirements

## Contract

- Must work without subagents.
- May use preserved framework subagents when the runtime supports it.
- Must not assume a blocking-question tool or a plugin-backed agent registry.
