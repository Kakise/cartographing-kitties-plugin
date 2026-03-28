---
name: cartograph:review
description: >
  Structured code review using Cartograph-powered reviewer agent swarms. Use when
  the user says "review this", "check my code", "code review", or before creating
  a PR. Dispatches always-on and conditional reviewer agents in parallel, merges
  findings, and optionally applies safe fixes. Supports modes: interactive (default),
  autofix (mode:autofix), report-only (mode:report-only).
argument-hint: "[branch|PR number] [mode:autofix|mode:report-only] [plan:path]"
---

# Cartograph: Review

Structured code review with **Cartograph-powered agent swarms** for structural
analysis beyond the diff.

## Mode Detection

| Mode | Token | Behavior |
|------|-------|----------|
| **Interactive** | (default) | Review, present findings, ask about fixes |
| **Autofix** | `mode:autofix` | Apply safe fixes automatically, no user interaction |
| **Report-only** | `mode:report-only` | Read-only analysis, no edits |

## Argument Parsing

Optional tokens in `$ARGUMENTS`:
- `mode:autofix` or `mode:report-only` — select mode
- `base:<sha-or-ref>` — use as diff base
- `plan:<path>` — load plan for requirements verification

## Severity Scale

| Level | Meaning | Action |
|-------|---------|--------|
| **P0** | Critical breakage, vulnerability, data loss | Must fix |
| **P1** | High-impact defect in normal usage | Should fix |
| **P2** | Edge case, perf regression, maintainability | Fix if easy |
| **P3** | Minor improvement | Discretion |

## Workflow

### Stage 1: Determine Scope

Compute the diff:
```bash
# Detect base branch
BASE=$(git merge-base HEAD main 2>/dev/null || echo "HEAD~1")
git diff --name-only $BASE
git diff -U10 $BASE
```

If `base:` argument provided, use it directly.

### Stage 2: Intent Discovery

Understand what changes accomplish from:
- Branch name + commit messages
- PR title/body (if PR number provided)
- Plan document (if `plan:` provided)

Write 2-3 line intent summary. Pass to every reviewer.

### Stage 3: Build Subgraph Context

Pre-compute structural graph context via MCP tools. Subagents cannot call MCP tools,
so the orchestrator gathers all graph data here and passes it as structured text.

#### 3a. Check Annotation Coverage

Call `annotation_status()`. Record coverage counts (annotated vs total nodes).
If more than 50% of nodes are unannotated, emit a warning:
> "WARNING: >50% of codebase nodes are unannotated. Review quality may be reduced — summaries, roles, and tags will be missing for many symbols. Consider running `cartograph:annotate` first."

#### 3b. File Structure for Modified Files

For each file in the diff file list, call `get_file_structure(path)`.

Collect all nodes from each file. Each node has: qualified_name, kind, line, summary, role, tags, annotation_status.

Cross-reference with the diff hunks to identify which specific symbols were modified
(a symbol is "modified" if any diff hunk overlaps its line range).

#### 3c. Query Neighbors for Modified Symbols

For each modified symbol identified in 3b, call `query_node(qualified_name)`.

Collect the neighbor lists (callers, callees, inherited classes, containers, dependents, dependencies). Each neighbor includes: qualified_name, kind, edge_kind, summary, role, tags.

#### 3d. Blast Radius for Public Symbols

For each modified symbol that is public (not prefixed with `_`), call
`find_dependents(qualified_name, max_depth=3)`.

Record transitive dependents at each depth level, including their summary, role, and tags.

#### 3e. Upstream Dependencies

For all modified symbols, call `find_dependencies(qualified_name)`.

Record what each symbol depends on, including summary, role, and tags.

#### 3f. Identify Edges Between Changed Nodes

From the neighbor data collected in 3c, identify all edges where BOTH source and target
are in the set of modified symbols. These are intra-change edges that reviewers need
to verify for contract consistency.

#### 3g. Format Subgraph Context Block

Assemble the collected data into a structured text block with these sections:

```
## Subgraph Context

### Annotation Status
- Total nodes: N
- Annotated: M (X%)
- WARNING (if applicable)

### Changed Nodes
| Qualified Name | Kind | Summary | Role | Tags | Location | Annotation Status |
|---|---|---|---|---|---|---|
| module.path::ClassName::method | method | "Does X" | "handler" | [api, auth] | src/foo.py:42 | annotated |
...

### Edges Between Changed Nodes
| Source | Target | Edge Kind |
|---|---|---|
| module::func_a | module::func_b | calls |
...

### Neighbors (1-hop)
For each changed node, list its callers and callees with summaries and roles:

#### module.path::ClassName::method
- CALLER: other_module::handler (role: "endpoint", summary: "Handles POST /users")
- CALLEE: db_module::save (role: "repository", summary: "Persists user record")
...

### Transitive Dependents (from find_dependents, max_depth=3)
| Qualified Name | Depth | Kind | Summary | Role | Tags |
|---|---|---|---|---|---|
| api.routes::create_user | 1 | function | "POST /users endpoint" | endpoint | [api] |
| tests.test_api::test_create_user | 2 | function | "Tests user creation" | test | [test] |
...

### Transitive Dependencies (from find_dependencies)
| Qualified Name | Kind | Summary | Role | Tags |
|---|---|---|---|---|
| db.models::User | class | "User ORM model" | model | [db, core] |
...
```

### Stage 4: Index & Dispatch Review Swarm

1. Call `index_codebase(full=false)` to ensure the graph reflects current changes
2. Dispatch reviewer agents in **parallel**, passing each agent: the diff, file list,
   intent summary, **subgraph context block** (from Stage 3), and plan (if provided):

**Always-on (every review):**
- **`cartograph-correctness-reviewer`** — Logic errors, edge cases, state bugs
- **`cartograph-testing-reviewer`** — Test coverage gaps via dependency analysis

**Conditional:**
- **`cartograph-impact-reviewer`** — When diff touches 3+ files or modifies public symbols
- **`cartograph-structure-reviewer`** — When new files are created or modules are added

### Stage 5: Merge & Deduplicate

Collect findings from all reviewers. Merge:
- Deduplicate by file + line (keep highest severity)
- If reviewers conflict, prefer the more conservative finding
- Sort by severity (P0 first), then by file

### Stage 6: Present or Apply

**Interactive mode:**
- Present findings grouped by severity
- For each P0/P1, ask: fix now, defer, or dismiss?
- Apply fixes the user approves

**Autofix mode (no user interaction):**
- Apply all `safe_auto` fixes automatically
- Write remaining findings to a review artifact
- Re-run tests after fixes
- If tests fail, revert last fix and continue

**Report-only mode:**
- Present findings summary
- Do NOT edit any files
- Return structured report

### Stage 7: Requirements Verification (if plan provided)

If a plan was loaded:
- Check each requirement (R1, R2...) against the diff
- Flag requirements with no corresponding changes
- Note any changes not traced to a requirement

## Tips

- Cartograph reviewers find issues grep-based reviews miss: unupdated dependents, broken contracts, circular dependencies
- `cartograph-impact-reviewer` catches the most critical issues — the "did you forget to update X?" findings
- Use `mode:autofix` in pipelines, `mode:report-only` for dry runs
- The subgraph context gives reviewers full structural awareness without needing MCP tool access
