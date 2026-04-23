---
name: kitty:work
description: >
  Execute implementation plans with Cartographing Kittens-first worker swarms. Use when the user
  says "build this", "implement", "execute the plan", "start working", or after planning.
  Each worker agent uses Cartographing Kittens to understand code before implementing. Supports
  inline execution by default with optional serial or parallel delegation when the runtime supports it.
argument-hint: "[plan file path]"
---

# Cartographing Kittens: Work

Execute plans with **Cartographing Kittens-first workflow steps**. Delegation is optional; the
default contract is inline execution with graph context gathered by the orchestrator.

## Workflow

### Phase 1: Setup

1. Read the plan document completely
2. Call `index_codebase(full=false)` to ensure the graph is fresh
3. Detect current branch — create feature branch or worktree if on main when the user wants branch isolation
4. Create task list from implementation units with dependencies

### Phase 2: Choose Execution Strategy

| Strategy | When | How |
|----------|------|-----|
| **Inline** | Default | Execute directly in the main conversation |
| **Serial delegation** | 3+ tasks with dependency chains | Delegate one task at a time when runtime support is clear |
| **Parallel delegation** | 3+ independent tasks | Delegate independent tasks simultaneously when runtime support is clear |
| **Swarm mode** | Not the default contract | Treat as aspirational/runtime-specific, not required |

**Default: Inline** — complete the work directly unless there is a clear benefit to delegation.

### Phase 3: Execute

For each implementation unit, the orchestrator follows this protocol:

**Cartographing Kittens-first context loading (orchestrator pre-computes):**

The orchestrator pre-computes graph context before either inline execution or optional delegation:
1. Call `get_file_structure` on every file in the unit's Files section
2. Call `query_node` on key symbols in those files
3. Call `find_dependents(name=key_symbol, max_depth=2)` per key symbol being modified — workers know what they might break (blast radius awareness)
4. Call `find_dependencies(name=key_symbol, max_depth=2)` per key symbol — workers understand upstream constraints
5. Call `annotation_status()` — warn worker if target area has low annotation coverage (<30%)
6. Call `rank_nodes(scope=unit_files)` — workers know which nodes need extra care (importance ranking)
7. Format as subgraph context (Annotation Status, Target Nodes, Neighbors, Dependents, Dependencies, Importance sections)
8. Include in the worker's task prompt alongside the plan unit

**Implementation loop (Observe → Understand → Act → Validate → Compound):**
```
For each task:
  1. OBSERVE — Mark task in-progress, load Cartographing Kittens context (above)
  2. UNDERSTAND — Review blast radius, upstream constraints, and importance rankings
  3. ACT — Read referenced files, implement following existing conventions, write tests
  4. VALIDATE — Run tests, fix failures immediately
     Post-implementation structural validation:
       a. Call index_codebase() to re-index changed files
       b. Call graph_diff(file_paths=changed_files) to see structural changes
       c. Call validate_graph(scope=changed_files) to check for new issues
     If graph_diff or validate_graph reveal unexpected breakage, fix before proceeding
  5. COMPOUND — Mark task completed, commit if logical unit is complete
```

**Optional delegation template:**

For each worker agent, provide:
- The full plan file path
- The specific unit (Goal, Files, Approach, Patterns, Test scenarios, Verification)
- The pre-computed graph context (file structures, node data with summaries, roles, and tags)
- Instruction: "Review the graph context provided, understand the purpose of each file/symbol from summaries and roles, then implement"

**Runtime-specific delegation:**
If the active runtime supports delegation cleanly, pass the plan unit plus the pre-computed graph
context to the preserved framework subagents. Do not assume `TaskCreate`, agent teams, or a swarm
registry as part of the required contract.

### Phase 4: Quality & Ship

1. Run full test suite
2. Run linter
3. Verify all tasks are completed
4. If plan has Requirements Trace, verify each requirement is satisfied
5. Commit with conventional format when the user wants a commit
6. Push and create PR only when explicitly requested or when the active runtime/workflow guarantees it

**PR template:**
```
## Summary
- What was built
- Key decisions made

## Testing
- Tests added/modified

## Cartographing Kittens Analysis
- Files touched: [count]
- Symbols modified: [from Cartographing Kittens]
- Blast radius: [from find_dependents]
```

### Execution Posture

Carry forward execution notes from the plan:
- **Test-first:** Write failing test before implementation
- **Characterization-first:** Capture existing behavior before changing
- **External-delegate:** Mark for delegation to another agent session when runtime support and task boundaries make it worthwhile

### Tips

- Workers should prefer the pre-computed graph context for understanding code structure, falling back to Read/Grep for source-level detail
- The orchestrator should call `find_dependents` after worker completion to check for unintended breakage
- Commit after each complete unit, not at the end
- If a unit reveals a plan gap, create a new task rather than deviating

## Contract

- Must work inline without subagents.
- May delegate when the runtime supports it cleanly.
- Must not require swarm primitives, background task registries, or automatic PR creation.
