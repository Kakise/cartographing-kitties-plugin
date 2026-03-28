---
name: cartograph:brainstorm
description: >
  Explore requirements and approaches through Cartograph-powered codebase understanding.
  Use when starting a new feature, exploring what to build, gathering requirements,
  or when the user says "let's brainstorm", "what should we build", "help me think through".
  Dispatches research agent swarms for parallel codebase analysis.
argument-hint: "[feature or problem description]"
---

# Cartograph: Brainstorm

Explore **WHAT** to build through dialogue and Cartograph-powered codebase analysis.
Produces a requirements document that feeds into `cartograph:plan`.

## Interaction Method

Use the platform's blocking question tool when available (AskUserQuestion in Claude Code).
Ask one question at a time.

## Workflow

### Phase 1: Index & Understand

1. Call `index_codebase(full=false)` to ensure the graph is fresh
2. If `$ARGUMENTS` is provided, use it as the feature description
3. If no arguments, ask: "What problem are you trying to solve or what feature are you considering?"

### Phase 2: Research Swarm

Dispatch these agents in **parallel** to understand the codebase context:

- **`cartograph-researcher`** — Scope: architecture, technology stack, module organization
- **`cartograph-pattern-analyst`** — Scope: existing patterns relevant to the feature area

Pass each agent the feature description as context.

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

**Pipeline mode:** If invoked from `cartograph:lfg` or another orchestrator, skip interactive questions. Infer requirements from the feature description and research findings.

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
[Key findings from Cartograph research — relevant patterns, architecture, existing code]

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
1. Start `cartograph:plan` with this requirements doc
2. Open requirements in editor for review
3. Continue refining requirements
