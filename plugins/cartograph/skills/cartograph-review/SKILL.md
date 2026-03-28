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

### Stage 3: Index & Dispatch Review Swarm

1. Call `index_codebase(full=false)` to ensure the graph reflects current changes
2. Dispatch reviewer agents in **parallel**:

**Always-on (every review):**
- **`cartograph-correctness-reviewer`** — Logic errors, edge cases, state bugs
- **`cartograph-testing-reviewer`** — Test coverage gaps via dependency analysis

**Conditional:**
- **`cartograph-impact-reviewer`** — When diff touches 3+ files or modifies public symbols
- **`cartograph-structure-reviewer`** — When new files are created or modules are added

Pass each agent: the diff, file list, intent summary, and plan (if provided).

### Stage 4: Merge & Deduplicate

Collect findings from all reviewers. Merge:
- Deduplicate by file + line (keep highest severity)
- If reviewers conflict, prefer the more conservative finding
- Sort by severity (P0 first), then by file

### Stage 5: Present or Apply

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

### Stage 6: Requirements Verification (if plan provided)

If a plan was loaded:
- Check each requirement (R1, R2...) against the diff
- Flag requirements with no corresponding changes
- Note any changes not traced to a requirement

## Tips

- Cartograph reviewers find issues grep-based reviews miss: unupdated dependents, broken contracts, circular dependencies
- `cartograph-impact-reviewer` catches the most critical issues — the "did you forget to update X?" findings
- Use `mode:autofix` in pipelines, `mode:report-only` for dry runs
