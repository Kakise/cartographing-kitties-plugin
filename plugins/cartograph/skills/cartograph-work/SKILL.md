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

**Cartograph-first context loading:**
1. Call `get_file_structure` on every file listed in the unit's Files section
2. Call `query_node` on key symbols to understand their neighbors
3. Read the unit's "Patterns to follow" files
4. Only then start implementing

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
- Instruction: "Start by calling get_file_structure and query_node on the target files before implementing"

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

- Workers should prefer Cartograph tools over grep/glob for understanding code
- Use `find_dependents` after modifications to check for unintended breakage
- Commit after each complete unit, not at the end
- If a unit reveals a plan gap, create a new task rather than deviating
