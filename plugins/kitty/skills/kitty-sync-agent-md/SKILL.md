---
name: kitty-sync-agent-md
description: |
  Audit paired CLAUDE.md / AGENTS.md memory files for section-structure drift — same H2 titles in both, identical bodies outside the project's allow-list, divergent runtime-specific bodies allowed where the title is allow-listed. Use when the user says "sync AGENTS.md", "are CLAUDE.md and AGENTS.md aligned", "check agent-md drift", "fix CLAUDE/AGENTS divergence", or "/kitty:sync-agent-md". Works on any project that ships both files for parallel Claude Code and Codex/OpenAI-flavored runtimes.
when_to_use: |
  Triggers: "sync agent md", "CLAUDE.md AGENTS.md drift", "check both memory files", "are CLAUDE/AGENTS aligned", "fix CLAUDE.md and AGENTS.md", "/kitty:sync-agent-md". Run after editing either file, and after any other skill (e.g. `kitty:bump-version`) writes new sections that need to be mirrored.
argument-hint: '[--fix]'
allowed-tools:
- Bash
- Read
- Edit
metadata:
  short-description: Drift checker for paired CLAUDE.md / AGENTS.md memory files.
---

Audit `CLAUDE.md` and `AGENTS.md` at the repository root. Both files
intentionally share the same H2 section structure; their bodies are allowed
to diverge only for runtime-specific sections (typically `Conventions`,
`Plugin Structure`, `MCP Tool Surface`, `MCP Server (local dev)` — confirm
per project).

## Rules

1. The set of `## ` H2 section titles must be identical across both files.
2. For every section NOT on the project's allow-list, the body text must be
   character-for-character identical.
3. Sections on the allow-list may diverge in body content but must still
   appear under the same heading in both files.

## How to run

If the `cartographing-kittens` package is installed and the project ships
`scripts/sync_claude_agents_md.py`:

```bash
uv run python scripts/sync_claude_agents_md.py --check
```

Otherwise, do it inline:

1. `Read` both `CLAUDE.md` and `AGENTS.md`.
2. Extract the H2 section list from each (lines matching `^## `).
3. Diff the title sets. Report any title present in one file but not the
   other.
4. For each title present in both, compare bodies. Skip sections on the
   project's allow-list (look for a constant like `CONTENT_ALLOWLIST` in
   `scripts/sync_claude_agents_md.py` if present; otherwise infer from
   section names — anything that names a runtime, plugin layout, or MCP
   surface is likely allow-listed).
5. Report drift in the form
   `<file>: section <title>: <description of difference>`.

## Fix mode

When `$ARGUMENTS` includes `--fix`:
- For missing sections, propose copying the section header (and a stub
   `TODO: align with <other file>` line) into the file that's missing it.
   Ask the user to confirm before writing.
- For body drift in non-allow-listed sections, propose syncing
   AGENTS.md ← CLAUDE.md by default (the project may pick the other
   direction; if so, follow the project's convention).
- Never auto-write without confirmation when the section body has clearly
   diverged on purpose — surface the diff and ask which side is canonical.

## Report

Print one line per drift item, then a summary like
`CLAUDE.md and AGENTS.md: <N> drift items across <K> sections (<M> in
allow-listed sections, ignored).` Exit 0 if no non-allow-listed drift.

## Notes

- This skill is project-agnostic. The allow-list of sections that may
  legitimately diverge lives in the project's own sync script — do not
  hardcode kitty's list when running against other repositories.
- Pre-commit hooks typically run this in `--check` mode; the skill is
  invoked when a human wants a richer diff and optional auto-fix.
