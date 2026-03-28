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

### Phase 1: Research Swarm

Call `index_codebase(full=false)` to ensure the graph is fresh.

Dispatch these agents in **parallel**:

- **`cartograph-researcher`** — Scope: architecture, technology, relevant modules
- **`cartograph-pattern-analyst`** — Scope: existing patterns for this kind of work
- **`cartograph-flow-analyzer`** — Scope: call chains and data flow in the affected area
- **`cartograph-impact-analyst`** — Scope: blast radius of proposed changes

Pass each agent the feature description and origin requirements as context.

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
- **Test scenarios** — specific input → expected outcome for each category:
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
