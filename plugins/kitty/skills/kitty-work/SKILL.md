---
name: kitty-work
description: |
  Execute implementation plans with Cartographing Kittens-first worker swarms. Use when the user says "build this", "implement", "execute the plan", "start working", or after planning. Each worker agent uses Cartographing Kittens to understand code before implementing. Supports inline execution by default with optional serial or parallel delegation when the runtime supports it. Requires the Cartographing Kittens MCP server (`uvx cartographing-kittens`).
when_to_use: |
  Triggers: "implement this", "build it", "execute the plan", "start working on units", "work the plan at <path>", "/kitty:work". Pairs with `kitty:plan` outputs in `docs/plans/`.
argument-hint: '[plan file path]'
disable-model-invocation: true
paths:
- docs/plans/*.md
allowed-tools:
- Read
- Edit
- Write
- Bash
- Grep
- Glob
- mcp__plugin_kitty_kitty__query_node
- mcp__plugin_kitty_kitty__get_file_structure
- mcp__plugin_kitty_kitty__find_dependents
- mcp__plugin_kitty_kitty__find_dependencies
- mcp__plugin_kitty_kitty__rank_nodes
- mcp__plugin_kitty_kitty__annotation_status
- mcp__plugin_kitty_kitty__graph_diff
- mcp__plugin_kitty_kitty__validate_graph
- mcp__plugin_kitty_kitty__query_litter_box
- mcp__plugin_kitty_kitty__query_treat_box
- mcp__plugin_kitty_kitty__add_litter_box_entry
- mcp__plugin_kitty_kitty__add_treat_box_entry
metadata:
  short-description: Execute an implementation plan with graph-aware blast-radius checks per unit.
requires:
  mcp_servers:
  - kitty
---

# Cartographing Kittens: Work

Execute plans with **Cartographing Kittens-first workflow steps**. Delegation is optional; the
default contract is inline execution with graph context gathered by the orchestrator.

<!-- entry-self-check -->
## Entry self-check (run first)

Slash-command invocation (`/kitty:kitty-work <plan>`) bypasses the `kitty` conductor, so this
gate runs at the top of the body regardless (spec §7):

- **Approved plan required.** Assert the plan file is present AND its frontmatter `status`
  is `ready`/`approved`, via the `plan_status` MCP tool. Otherwise refuse and route to
  `kitty:plan`.
- **Attach the run journal.** Lazily create/attach `.pawprints/runs/<run-id>/` if the
  conductor did not, recording the absolute `plan_path` in the journal header.

## Workflow

### Phase 1: Setup

1. Read the plan document completely
2. Call `index_codebase(full=false)` to ensure the graph is fresh
3. Run memory preflight using `kitty/references/memory-workflow.md`:
   - Call `query_litter_box(limit=20)` and `query_treat_box(limit=20)`
   - Query the strongest plan/unit terms with `search=<term>`
   - Add relevant lessons to the implementation context for every affected unit
4. Detect current branch. If on `main` or another protected branch and the user
   has not specified a branch strategy, issue an `AskUserQuestion` (single-select,
   header `"Branch"`, recommended option first) per
   `kitty/references/ask-user-protocol.md`:

   ```yaml
   question: "You are on `main` and the plan modifies tracked files. How should we isolate the work?"
   header: "Branch"
   multiSelect: false
   options:
     - label: "Create feature branch (Recommended)"
       description: "Branch off main, work there, leave main untouched."
     - label: "Create a worktree"
       description: "Isolate the change in a separate worktree."
     - label: "Stay on current branch"
       description: "Edit in place — only safe if the user explicitly accepts."
   ```

   Skip the prompt when the user already specified a branch strategy or when
   running in pipeline mode (use the recommended option).
5. Create task list from implementation units with dependencies

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
8. Include `### Memory Context` from the preflight:
   - Litter lessons this unit must avoid
   - Treat lessons this unit should follow
   - Explicit note when no relevant memory exists
9. Include in the worker's task prompt alongside the plan unit

**Implementation loop (Observe → Understand → Act → Validate → Compound):**
```
For each task:
  1. OBSERVE — Mark task in-progress (update plan state — see "Plan-state
     updates" below), load Cartographing Kittens context (above)
  2. UNDERSTAND — Review blast radius, upstream constraints, and importance rankings
  3. ACT — Read referenced files, implement following existing conventions, write tests
  4. VALIDATE — Run tests, fix failures immediately
     Post-implementation structural validation:
       a. Call index_codebase() to re-index changed files
       b. Call graph_diff(file_paths=changed_files) to see structural changes
       c. Call validate_graph(scope=changed_files) to check for new issues
     If graph_diff or validate_graph reveal unexpected breakage, fix before proceeding
  5. COMPOUND — Mark task completed (update plan state with the commit
     hash), commit if logical unit is complete
```

**Plan-state updates:**

Each unit transition must be reflected in the plan file's frontmatter and
per-unit `**State:**` line so the dashboard (`kitty-plan-status report` or
`/kitty:kitty-plans`) and downstream skills see live progress. Use the
installed console script when available; fall back to the in-repo path:

```bash
# When starting a unit (OBSERVE):
kitty-plan-status set-unit <plan-path> <unit-id> in_progress
# In-repo fallback:
uv run python scripts/plan_status.py set-unit <plan-path> <unit-id> in_progress

# When the unit lands (COMPOUND), include the commit hash:
kitty-plan-status set-unit <plan-path> <unit-id> complete --commit "$(git rev-parse HEAD)"
```

Never hand-edit the unit `**State:**` lines or frontmatter `state:` values —
go through `kitty-plan-status` so the parser stays the single source of
truth. If a unit is intentionally dropped, use `--reason "<why>"` with
`state=skipped` rather than deleting the unit.

**Memory postflight:**

After each completed unit, record durable lessons only when validated:
- Call `add_litter_box_entry` for failures, regressions, unsupported approaches, flaky tests,
  or anti-patterns discovered while implementing.
- Call `add_treat_box_entry` for patterns validated by code changes and tests.
- Use `source_agent="kitty:work"` unless a delegated worker is clearly responsible.

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
5. When every unit reaches `complete`, mark the plan itself complete and
   stamp it with the final commit hash so the dashboard reflects shipped
   state:

   ```bash
   kitty-plan-status set-status <plan-path> complete --implemented-in "$(git rev-parse HEAD)"
   # In-repo fallback:
   uv run python scripts/plan_status.py set-status <plan-path> complete --implemented-in "$(git rev-parse HEAD)"
   ```

   Skip this step if any unit is still `pending` or `in_progress` — leave
   the plan at `in_progress` so a future `kitty:work` session can resume
   from where it stopped.
6. Summarize memory usage: queried entries, applied lessons, and newly recorded lessons
7. When uncommitted changes exist and the user has not specified a commit
   strategy, issue an `AskUserQuestion` (single-select, header `"Commit"`,
   recommended option first) per `kitty/references/ask-user-protocol.md`:

   ```yaml
   question: "Implementation is complete with uncommitted changes. How should we land them?"
   header: "Commit"
   multiSelect: false
   options:
     - label: "Commit now (Recommended)"
       description: "Create a conventional-format commit with the implementation summary."
     - label: "Stage for review"
       description: "Run `git add` only; leave the commit message to the user."
     - label: "Leave dirty"
       description: "Do not stage or commit; the user will handle git themselves."
   ```

   Skip the prompt when the user already specified a commit strategy or in
   pipeline mode (use the recommended option, but fall back to "Leave dirty" if
   tests are failing).
8. Push and create PR only when explicitly requested or when the active
   runtime/workflow guarantees it. Do not auto-prompt for push/PR — keep the
   default to require explicit user request.

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
- Must query litter/treat memory before implementation and record validated durable lessons after work.
- Must update plan state via `kitty-plan-status set-unit` (or
  `scripts/plan_status.py` in-repo) on every unit transition so the plan
  file stays the source of truth for progress — never hand-edit `**State:**`
  or frontmatter `state:` values.
- Must issue branch-strategy and commit-strategy prompts via `AskUserQuestion`
  per `kitty/references/ask-user-protocol.md`. Pipeline mode skips both prompts.

## Orchestration

- **Entry self-check:** required — refuses unless an approved plan exists via the plan_status MCP tool, else routes to kitty-plan
