---
name: kitty:brainstorm
description: >
  Explore requirements and approaches through Cartographing Kittens-powered codebase understanding.
  Use when starting a new feature, exploring what to build, gathering requirements,
  or when the user says "let's brainstorm", "what should we build", "help me think through".
  Dispatches research agent swarms for parallel codebase analysis.
argument-hint: "[feature or problem description]"
---

# Cartographing Kittens: Brainstorm

Explore **WHAT** to build through dialogue and Cartographing Kittens-powered codebase analysis.
Produces a requirements document that feeds into `kitty:plan`.

## Interaction Method

Use the platform's blocking question tool when available (AskUserQuestion in Claude Code).
Ask one question at a time.

## Workflow

### Phase 1: Index & Understand

1. Call `index_codebase(full=false)` to ensure the graph is fresh
2. If `$ARGUMENTS` is provided, use it as the feature description
3. If no arguments, ask: "What problem are you trying to solve or what feature are you considering?"

### Phase 2: Research Swarm

**Build the subgraph context before dispatching agents:**

1. **Annotation status** — Call `annotation_status()`. Record total nodes, annotated count, and coverage percentage.

2. **Search for relevant nodes** — Call `search` with 2-4 feature-area keywords extracted from the feature description. Collect matching qualified names, file paths, summaries, tags, and roles.

3. **File structures** — Call `get_file_structure` on the top 3-5 files identified by search results. Capture node listings with kinds, summaries, tags, and roles.

4. **Key symbol details** — Call `query_node` on the 3-5 most important symbols from search results (classes, entry points, core functions). Capture their metadata and neighbors.

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
```

**Dispatch these agents in parallel**, passing each the feature description AND the formatted subgraph context:

- **`librarian-kitten-researcher`** — Pass: full subgraph context (annotation status, target nodes, file structures, symbol details). Scope: architecture, technology stack, module organization
- **`librarian-kitten-pattern`** — Pass: search results and file structures from the subgraph context. Scope: existing patterns relevant to the feature area

Collect findings: technology stack, relevant patterns, key files, existing conventions.

### Phase 3: Adaptive Questioning

Use research findings to ask targeted questions. Ask **one question at a time**:

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
