---
name: kitty-validate-skills
description: |
  Validate Claude Code SKILL.md files against the official spec (name format, description length, allowed-tools naming, body line limit, referenced files). Use when the user says "validate my skills", "check skill compliance", "audit SKILL.md", "lint skills", or "/kitty:validate-skills". Works on any project's `.claude/skills/` or `plugins/*/skills/` tree, not just kitty's.
when_to_use: |
  Triggers: "validate skills", "lint SKILL.md", "check Claude Code skill spec", "audit my skills directory", "/kitty:validate-skills".
argument-hint: '[skills-dir] [--strict]'
allowed-tools:
- Bash
- Read
- Grep
- Glob
metadata:
  short-description: Spec-compliance checker for Claude Code skill frontmatter.
---

Validate Claude Code SKILL.md files against the spec at
https://code.claude.com/docs/en/skills and the best-practices guide at
https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.

## Pick the skills root

- If `$ARGUMENTS` names a directory, use that.
- Otherwise, look for skills in this order and use the first match:
  1. `plugins/*/skills/`
  2. `.claude/skills/`
  3. `skills/`
- If none exist, report that no skills directory was found and stop.

## Validation rules

For each `SKILL.md` under the skills root, check:

1. **YAML frontmatter** opens with `---\n` and closes with `\n---\n`.
2. **`name`** matches `^[a-z0-9-]{1,64}$` — lowercase, numbers, hyphens only.
   No colons (the plugin namespace prefix is added by Claude Code at load
   time from the plugin manifest, not encoded in the skill name).
3. **`description`** is non-empty and ≤ 1024 chars after stripping. Leads with
   a phrase a user would actually type.
4. **`when_to_use`** (optional) is ≤ 1024 chars. Combined `description` +
   `when_to_use` ≤ 1536 chars when Claude lists the skill.
5. **`argument-hint`** is present whenever the body references `$ARGUMENTS`.
6. **`allowed-tools`** entries are either:
   - Built-in tools by short name (`Read`, `Grep`, `Glob`, `Bash`, `Write`,
     `Edit`, `Task`), or
   - MCP tools with the fully-qualified
     `mcp__plugin_<plugin>_<server>__<tool>` form. Unprefixed MCP names like
     `mcp__server__tool` fail validation.
7. **Body** is ≤ 500 lines; longer prose belongs in sibling `references/`
   files.
8. **Referenced files** mentioned in the body (path tokens ending in `.md`
   under `references/`) exist on disk.

## How to run

If the `cartographing-kittens` package is installed (e.g. via
`uv tool install cartographing-kittens` or as a dev dep), prefer the bundled
console script — it implements the full ruleset above:

```bash
uv run kitty-validate-skills
# or, when on PATH:
kitty-validate-skills
```

Otherwise, walk the directory yourself with `Glob` + `Read` and apply the
rules above. Use `--strict` (when passed in `$ARGUMENTS`) to also fail on
warnings (overlong descriptions, missing `when_to_use` on high-traffic
skills, etc.).

## Report

Output one line per violation in the form
`<path>: <field>: <issue> (rule N)`. Exit success with no output when all
skills pass. Summarize at the end:
`<N> skills checked, <M> violations across <K> files.`

## Notes

- This skill does NOT regenerate skills from sources — for that, use the
  project's own generator (kitty uses `scripts/generate_skills.py`).
- For plugin-namespaced skills, double-check the plugin manifest's `name`
  against the MCP tool prefix expected in `allowed-tools` — a mismatch
  silently denies the tool at runtime.
