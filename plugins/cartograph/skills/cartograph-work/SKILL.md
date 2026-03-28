---
name: cartograph:work
description: >
  Execute implementation plans with Cartograph-first worker swarms. Use when the user
  says "build this", "implement", "execute the plan", "start working", or after planning.
  Each worker agent uses Cartograph to understand code before implementing. Supports
  inline, serial, parallel, and full swarm execution strategies.
argument-hint: "[plan file path]"
---

# Cartograph: Work

Execute plans with **Cartograph-first worker agents** — every worker understands the
code structure before implementing.

## Workflow

### Phase 1: Setup

1. Read the plan document completely
2. Call `index_codebase(full=false)` to ensure the graph is fresh
3. Detect current branch — create feature branch or worktree if on main
4. Create task list from implementation units with dependencies

### Phase 2: Choose Execution Strategy

| Strategy | When | How |
|----------|------|-----|
| **Inline** | 1-2 small tasks | Execute directly, no subagents |
| **Serial subagents** | 3+ tasks with dependency chains | One agent at a time, in dependency order |
| **Parallel subagents** | 3+ independent tasks | Dispatch all independent tasks simultaneously |
| **Swarm mode** | 10+ tasks, complex coordination | Agent Teams with persistent roles |

**Default: Parallel subagents** — dispatch independent tasks as a swarm.

### Phase 3: Execute

For each implementation unit, the worker agent follows this protocol:

**Cartograph-first context loading (orchestrator pre-computes):**

The orchestrator pre-computes graph context for each worker before dispatch:
1. Call `get_file_structure` on every file in the unit's Files section
2. Call `query_node` on key symbols in those files
3. Format as subgraph context (Annotation Status, Target Nodes, Neighbors sections)
4. Include in the worker's task prompt alongside the plan unit

**Implementation loop:**
```
For each task:
  1. Mark task in-progress
  2. Load Cartograph context (above)
  3. Read referenced files from plan
  4. Implement following existing conventions
  5. Write tests matching plan's test scenarios
  6. Run tests — fix failures immediately
  7. Mark task completed
  8. Commit if logical unit is complete
```

**Subagent dispatch template:**

For each worker agent, provide:
- The full plan file path
- The specific unit (Goal, Files, Approach, Patterns, Test scenarios, Verification)
- The pre-computed graph context (file structures, node data with summaries, roles, and tags)
- Instruction: "Review the graph context provided, understand the purpose of each file/symbol from summaries and roles, then implement"

**Swarm mode (Agent Teams):**
1. Create team with TaskCreate
2. Create tasks from implementation units with dependencies
3. Spawn worker agents — each claims a task, loads Cartograph context, implements
4. Monitor: reassign stuck workers, spawn more as phases unblock
5. Cleanup when all tasks complete

### Phase 4: Quality & Ship

1. Run full test suite
2. Run linter
3. Verify all tasks are completed
4. If plan has Requirements Trace, verify each requirement is satisfied
5. Commit with conventional format
6. Push and create PR

**PR template:**
```
## Summary
- What was built
- Key decisions made

## Testing
- Tests added/modified

## Cartograph Analysis
- Files touched: [count]
- Symbols modified: [from Cartograph]
- Blast radius: [from find_dependents]
```

### Execution Posture

Carry forward execution notes from the plan:
- **Test-first:** Write failing test before implementation
- **Characterization-first:** Capture existing behavior before changing
- **External-delegate:** Mark for delegation to another agent session

### Tips

- Workers should prefer the pre-computed graph context for understanding code structure, falling back to Read/Grep for source-level detail
- The orchestrator should call `find_dependents` after worker completion to check for unintended breakage
- Commit after each complete unit, not at the end
- If a unit reveals a plan gap, create a new task rather than deviating
