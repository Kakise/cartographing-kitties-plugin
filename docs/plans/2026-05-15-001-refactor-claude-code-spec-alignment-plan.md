---
title: Align Skills and Subagents with Claude Code 2026 Spec
type: refactor
status: complete
date: 2026-05-15
implemented_in: pending
units:
  - id: 1
    title: Update CLAUDE.md and AGENTS.md with Claude Code spec citations
    state: complete
  - id: 2
    title: Fix skill source YAMLs (frontmatter spec compliance)
    state: complete
  - id: 3
    title: Fix subagent source YAMLs (MCP tool access)
    state: complete
  - id: 4
    title: Strengthen `scripts/validate_skills.py` for Claude Code spec
    state: complete
  - id: 5
    title: Fix invalid agent color and add color validator
    state: complete
---

# Align Skills and Subagents with Claude Code 2026 Spec

## Overview

Audit and tighten every `plugins/kitty/_source/skills/*.yaml` and
`plugins/kitty/_source/agents/*.yaml` against the current (May 2026) Claude
Code documentation for SKILL.md frontmatter and custom subagents, then update
`CLAUDE.md` / `AGENTS.md` so future authoring follows the same spec.

This is a refactor, not a feature: no new behavior, but several real
misalignments will be corrected and the generators/validator made stricter so
drift cannot return.

## Problem Frame

Three concrete misalignments surfaced during a 2026-05-15 spec audit:

1. **Skill `name:` frontmatter contains colons.** Source YAMLs declare
   `name: kitty:plan`, `name: kitty:explore`, etc. The Claude Code spec
   requires `name` to be "lowercase letters, numbers, and hyphens only (max 64
   characters)" with no colons (https://code.claude.com/docs/en/skills,
   "Frontmatter reference"). The plugin namespace `kitty:` is **applied
   automatically** by Claude Code from the directory name, so writing
   `kitty:plan` either (a) silently falls back to directory name `kitty-plan`,
   producing the working `/kitty:kitty-plan` command users already type, or
   (b) is loaded but invalid. Either way it is non-compliant.

2. **Subagent `tools:` field excludes the MCP tools the agents claim to
   use.** Every generated agent file under `plugins/kitty/agents/*.md`
   declares `tools: Read, Grep, Glob` while the developer instructions tell
   the agent to "use `query_node` / `find_dependents` / etc." Per the spec
   (https://code.claude.com/docs/en/sub-agents, "Available tools"), when
   `tools:` is set the subagent gets **only** that allowlist — every other
   tool, including all MCP tools, is denied. Agents therefore cannot actually
   call kitty MCP tools. The `mcp_tools:` field is a custom kitty invention
   that Claude Code ignores.

3. **`allowed-tools` in skills uses short MCP tool names.** Skill YAMLs list
   `allowed-tools: [query_node, search, ...]`. Claude Code registers MCP
   tools as `mcp__<server>__<tool>` (here:
   `mcp__plugin_kitty_kitty__query_node`). The validator already accepts both
   forms via a `__` split heuristic, but the actual permission pre-approval
   only matches the namespaced form.

In addition, the description fields are long but do not lead with trigger
phrases the way Anthropic's
[best-practices guide](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
recommends, and there is no `when_to_use` field anywhere — that field exists
specifically to feed trigger keywords to Claude's discovery without bloating
the always-visible description.

CLAUDE.md / AGENTS.md document the Cartographing Kittens framework well but
do not point readers to the official spec, do not state the MCP tool naming
rule, and do not record the plugin-namespacing rule.

## Requirements Trace

- **R1 — Spec compliance.** Skill frontmatter must satisfy the Claude Code
  validation rules: `name` is lowercase-hyphen-only ≤64 chars; `description`
  ≤1024 chars; body ≤500 lines.
- **R2 — Subagents can actually use MCP tools.** Every framework subagent
  that mentions an MCP tool in its body must either omit `tools:` (inherit
  all) or list the fully-qualified MCP tool name(s) in `tools:`.
- **R3 — Discovery accuracy.** Each skill description leads with the user
  intent it serves, and trigger phrases live in `description` or
  `when_to_use` so Claude's fuzzy matcher actually fires.
- **R4 — Drift protection.** `scripts/validate_skills.py` enforces R1, the
  generators reflect the corrected source, and CLAUDE.md / AGENTS.md cite the
  Anthropic spec so future authors stay aligned.

## Scope Boundaries

**In scope**

- All ten skill source YAMLs under `plugins/kitty/_source/skills/`.
- All ten agent source YAMLs under `plugins/kitty/_source/agents/`.
- `scripts/validate_skills.py` and its test (`tests/test_skill_validator.py`).
- `scripts/generate_agents.py` and the `agent.claude.md.j2` template if the
  tools-field decision requires template changes.
- `CLAUDE.md`, `AGENTS.md`, and the sync allow-list in
  `scripts/sync_claude_agents_md.py` if a new H2 is added to one and not the
  other.

**Out of scope**

- Renaming skill directories (e.g. `kitty-plan/` → `plan/`). That would let
  the command be `/kitty:plan` instead of `/kitty:kitty-plan`, but it touches
  hundreds of cross-references and is a separate UX decision. We document
  the current `/kitty:kitty-*` convention and leave the renaming for a
  future plan.
- Any change to the MCP server itself (`src/cartograph/server/`).
- Any change to Codex TOML output beyond what the generator naturally
  produces from corrected YAML.
- Adding `disable-model-invocation` / `user-invocable` to any skill — current
  defaults are correct for our workflow.

## Context & Research

### Authoritative sources (fetched 2026-05-15)

- Claude Code Skills doc — https://code.claude.com/docs/en/skills
- Subagent doc — https://code.claude.com/docs/en/sub-agents
- Skill authoring best practices —
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Anthropic skill-creator SKILL.md —
  https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md

### Key rules confirmed by these sources

- `name`: lowercase + numbers + hyphens, ≤64 chars, no XML tags, no reserved
  words (`anthropic`, `claude`).
- `description`: ≤1024 chars; the combined description + `when_to_use` is
  truncated at 1,536 chars in the listing.
- Tools field is a space-separated string **or** YAML list — both work; the
  generator currently emits comma-separated which is also accepted.
- Setting `tools:` is an **allowlist** — anything not listed (including MCP
  tools) is denied. To restrict from a base of "inherit everything", use
  `disallowedTools:` instead.
- MCP tools are referenced as `mcp__<server>__<tool>` in `tools:` /
  `allowed-tools:`. For this repo, the prefix is
  `mcp__plugin_kitty_kitty__`.
- Skill body should stay under 500 lines; the validator already enforces this.
- Agent descriptions perform better when they include "Use proactively …" or
  "Use when …" trigger phrases per the spec examples.

### Subgraph snapshot (relevant nodes)

- `scripts/validate_skills.py::KNOWN_TOOLS` is the canonical list of accepted
  short tool names; touching `allowed-tools` requires synchronized updates
  here (validated in treat-box entry 7).
- `scripts/generate_agents.py::_load_agent_sources` accepts arbitrary extra
  YAML keys and forwards them to the template; only the six required keys
  are enforced (treat-box entry 6).
- `scripts/sync_claude_agents_md.py` enforces H2 parity between CLAUDE.md
  and AGENTS.md with a content allow-list (treat-box entry 5).

## Key Technical Decisions

1. **Drop `name:` with colons.** Set each skill's `name:` to match its
   directory (e.g. `name: kitty-plan`). This makes the YAML spec-compliant
   without changing the actual slash command (`/kitty:kitty-plan` still works
   because plugin namespacing prepends `kitty:`). Documentation inside skill
   bodies continues to refer to the conceptual short forms ("kitty:plan",
   "kitty:work") since that prose is human-facing, not a slash command.

2. **Subagent MCP access via inheritance, not enumeration.** Remove the
   `tools:` field entirely from agents that need MCP tools, letting them
   inherit the full tool set from the main conversation. Listing
   `mcp__plugin_kitty_kitty__query_node` etc. would work but bloats
   frontmatter and requires per-tool maintenance. The `mcp_tools:` custom
   field is dropped from the template output (kept in YAML only as
   documentation of intent, OR removed entirely — Unit 3 decides).

3. **`allowed-tools` keeps short names + namespaced fallback.** Update the
   skill YAMLs to use the namespaced `mcp__plugin_kitty_kitty__*` form so
   Claude Code's permission pre-approval matches. The validator's
   `KNOWN_TOOLS` set is extended to accept both forms (it already splits on
   `__`, but the recognized set must enumerate the prefixed names too, so
   typos in the prefix are caught).

4. **Add `when_to_use` to high-traffic skills.** `kitty`, `kitty-plan`,
   `kitty-work`, `kitty-review`, `kitty-impact`, `kitty-explore` get an
   explicit `when_to_use:` listing trigger phrases. The shorter skills
   (`kitty-install-codex`, `kitty-lfg`) keep just `description:` — they
   already lead with a clear trigger.

5. **Validator strictness.** `validate_skills.py` adds three new checks:
   `name` matches `^[a-z0-9-]{1,64}$`; `description` length ≤1024;
   `when_to_use` length ≤1024. Plus a check that any `mcp__` prefix matches
   the canonical `mcp__plugin_kitty_kitty__` for this plugin. The existing
   500-line body check stays.

## Open Questions

- Should we also rename `kitty-plan/` → `plan/` so the command becomes
  `/kitty:plan` (cleaner) instead of `/kitty:kitty-plan`? **Deferred** —
  out of scope for this plan, opened as a follow-up since the directory
  rename touches every docs/plans cross-reference. Pipeline-mode pick:
  defer.
- Should `mcp_tools:` be deleted from YAML entirely now that the template
  ignores it, or kept as documentation? **Pipeline-mode pick:** delete it.
  The intent is now captured by the developer instructions, and dead YAML
  fields are confusing.
- Should agent descriptions adopt the "Use proactively …" phrasing? Yes for
  always-on reviewers (`expert-kitten-correctness`, `expert-kitten-testing`)
  and the annotation specialist; the conditional reviewers keep "Spawned
  when …".

## Memory Context

- **Litter lessons to avoid:** No relevant litter-box entries returned for
  the searched terms (`skill`, `subagent`, `frontmatter`, `tools`).
- **Treat lessons to follow:**
  - [validated-pattern] When changing `allowed-tools` in skill frontmatter,
    `scripts/validate_skills.py::KNOWN_TOOLS` must be updated in the same
    logical change; test_skill_validator and test_plugin_packaging will catch
    drift otherwise (treat #7).
  - [validated-pattern] Generator passes unknown YAML fields through to the
    template render context but only validates the six required keys
    (`name|description|role|model|tools|developer_instructions`). Dropping
    unused fields like `mcp_tools` from YAML does not break the generator
    (treat #6).
  - [validated-pattern] The CLAUDE.md/AGENTS.md sync checker is H2-section-
    token-based with a content allow-list; new H2 sections must appear in
    both files, with byte identity unless allow-listed (treat #5).
  - [convention] Skills must use Claude Code's `AskUserQuestion` tool for
    every interactive prompt with 2–4 enumerable options; pipeline modes
    skip prompts. The skill-frontmatter rewrites must not regress this
    (treat #1).
- **Memory gaps:** No prior lesson recorded about subagent MCP-tool access
  via the `tools:` field. This plan's Unit 3 validation should produce a
  new treat-box entry.

## Implementation Units

### Unit 1 — Update CLAUDE.md and AGENTS.md with Claude Code spec citations

**State:** complete

**Goal.** Add a short "Skill and Subagent Authoring" section to both
CLAUDE.md and AGENTS.md that records the spec rules future authors must
follow, with citations to the live docs.

**Requirements.** R4.

**Dependencies.** None.

**Files.**
- `CLAUDE.md` — add new H2 `## Skill and Subagent Authoring` immediately
  after the existing `## Conventions` section.
- `AGENTS.md` — same H2, byte-identical or allow-listed body.
- `scripts/sync_claude_agents_md.py` — extend the allow-list only if the
  body content needs to differ between files (it should not).

**Approach.**

Document, in <50 lines, the following spec rules:
- `name:` must match `^[a-z0-9-]{1,64}$`; colons come from the plugin
  namespace, not the YAML.
- `description:` ≤1024 chars, leads with the trigger phrase.
- `when_to_use:` is the recommended place for additional trigger keywords.
- `allowed-tools:` lists MCP tools as `mcp__plugin_kitty_kitty__<tool>`.
- Body ≤500 lines; move detail to `references/`.
- For subagents: setting `tools:` is an **allowlist** that excludes all
  unlisted tools, including MCP. Omit `tools:` to inherit; list
  `mcp__plugin_kitty_kitty__<tool>` explicitly when narrowing.

Cite the four authoritative URLs at the end.

**Patterns to follow.** The existing `## Conventions` H2 uses a bullet list;
the new H2 mirrors that style.

**Test scenarios.**
- Happy path: pre-commit hook `kitty-sync-claude-agents-md` passes after
  editing both files identically.
- Edge case: intentional drift fails the hook (verified by adding one extra
  bullet to CLAUDE.md and reverting after the hook fires).

**Verification.**
- `uv run python scripts/sync_claude_agents_md.py --check` passes.
- `git diff CLAUDE.md AGENTS.md` shows the same H2 section in both.

---

### Unit 2 — Fix skill source YAMLs (frontmatter spec compliance)

**State:** complete

**Goal.** Bring every `_source/skills/*.yaml` into compliance with the
Claude Code spec: drop colon-containing names, add `when_to_use` where it
helps discovery, and use namespaced MCP tool names in `allowed-tools`.

**Requirements.** R1, R3.

**Dependencies.** Unit 4's validator changes are not a hard dependency, but
landing Unit 4 in the same PR avoids a transient state where the YAMLs pass
the old validator but not the new one. Order in PR: Unit 2 → Unit 4 →
regenerate.

**Files.** All ten:
- `plugins/kitty/_source/skills/kitty.yaml`
- `plugins/kitty/_source/skills/kitty-annotate.yaml`
- `plugins/kitty/_source/skills/kitty-brainstorm.yaml`
- `plugins/kitty/_source/skills/kitty-explore.yaml`
- `plugins/kitty/_source/skills/kitty-impact.yaml`
- `plugins/kitty/_source/skills/kitty-install-codex.yaml`
- `plugins/kitty/_source/skills/kitty-lfg.yaml`
- `plugins/kitty/_source/skills/kitty-plan.yaml`
- `plugins/kitty/_source/skills/kitty-review.yaml`
- `plugins/kitty/_source/skills/kitty-work.yaml`

Plus the regenerated outputs under `plugins/kitty/skills/<name>/SKILL.md`.

**Approach.**

For each YAML:
1. Replace `name: kitty:foo` with `name: kitty-foo` (matches directory).
   The router skill `kitty/` already has `name: kitty` — leave as-is.
2. Verify `description:` is ≤1024 chars; if it exceeds, split the trailing
   sentences into a new `when_to_use:` field.
3. Reorder `description:` so it leads with the action verb and the key
   trigger phrase (per Anthropic best practices: "Lead with the trigger
   phrase a user would actually type").
4. Add `when_to_use:` to: `kitty`, `kitty-plan`, `kitty-work`,
   `kitty-review`, `kitty-impact`, `kitty-explore`. Use 2–4 short trigger
   examples each, ≤300 chars total.
5. Convert `allowed-tools:` MCP entries from `query_node` to
   `mcp__plugin_kitty_kitty__query_node`. Built-in tools (`Read`, `Grep`,
   `Glob`, `Bash`, `Write`, `Edit`) keep their short names.
6. Regenerate: `uv run python scripts/generate_skills.py`.
7. Validate: `uv run python scripts/validate_skills.py`.

**Patterns to follow.** The existing structure of `kitty.yaml`'s
`frontmatter.requires.mcp_servers` is the model for namespaced references.

**Test scenarios.**
- Happy path: generator runs cleanly; `--check` passes after the rewrite.
- Edge case: deliberately set `name: kitty:plan` and confirm the new
  validator (Unit 4) flags it.
- Integration: invoke `/kitty:kitty-plan` end-to-end in a smoke test (manual
  — note in plan that automation is out of scope).

**Verification.**
- `uv run python scripts/generate_skills.py --check` exits 0 after the
  generator runs.
- `uv run python scripts/validate_skills.py` exits 0.
- Every generated SKILL.md has `name: kitty-<foo>` (no colon) except
  `kitty/SKILL.md` which keeps `name: kitty`.

---

### Unit 3 — Fix subagent source YAMLs (MCP tool access)

**State:** complete

**Goal.** Make every framework subagent actually able to call the MCP tools
its developer_instructions describe. Drop the `mcp_tools:` custom field.

**Requirements.** R2.

**Dependencies.** None (independent of Unit 2). Can land in same PR.

**Files.**
- `plugins/kitty/_source/agents/cartographing-kitten.yaml`
- `plugins/kitty/_source/agents/expert-kitten-context.yaml`
- `plugins/kitty/_source/agents/expert-kitten-correctness.yaml`
- `plugins/kitty/_source/agents/expert-kitten-impact.yaml`
- `plugins/kitty/_source/agents/expert-kitten-structure.yaml`
- `plugins/kitty/_source/agents/expert-kitten-testing.yaml`
- `plugins/kitty/_source/agents/librarian-kitten-flow.yaml`
- `plugins/kitty/_source/agents/librarian-kitten-impact.yaml`
- `plugins/kitty/_source/agents/librarian-kitten-pattern.yaml`
- `plugins/kitty/_source/agents/librarian-kitten-researcher.yaml`

`scripts/generate_agents.py` — drop the `mcp_tools` default and stop
emitting `mcp_tools:` to the template context if any template referenced
it (none currently do — confirmed via `grep mcp_tools
plugins/kitty/_source/templates/*.j2` ⇒ no hits).

`plugins/kitty/_source/templates/agent.claude.md.j2` — current template
unconditionally emits `tools: {{ tools|join(", ") }}`. Change so that an
empty `tools` list omits the line entirely (inherits in Claude Code).

**Approach.**

For each agent YAML:
1. Decide tool posture:
   - **`cartographing-kitten`** (the batch annotator) explicitly says "You
     do NOT call any MCP tools" in its body. Keep `tools: [Read, Grep,
     Glob, Bash]` as a tight allowlist.
   - **All `librarian-*` and `expert-*`** agents call MCP tools in their
     workflow. Set `tools: []` so the template omits the field and Claude
     Code inherits the parent's full tool set (including MCP).
2. Delete the `mcp_tools:` field. The information about which MCP tools
   each agent uses lives in `developer_instructions` already.
3. Update `scripts/generate_agents.py::_load_agent_sources` to remove the
   `agent.setdefault("mcp_tools", [])` line so the field stops being a
   default.
4. Update `agent.claude.md.j2`: wrap `tools:` in a Jinja conditional so an
   empty list omits the line.
5. Regenerate: `uv run python scripts/generate_agents.py`.

**Patterns to follow.** The omitted-when-empty pattern is already used for
`color` in the template; mirror it for `tools`.

**Test scenarios.**
- Happy path: a librarian agent regenerates with no `tools:` line; a
  Codex TOML still serializes correctly (since Codex TOML doesn't include
  tools).
- Edge case: `cartographing-kitten` still emits `tools: Read, Grep, Glob,
  Bash` because its list is non-empty.
- Error path: a YAML with `tools: null` raises a clear error in the loader.
- Integration: spawn `expert-kitten-correctness` through `kitty:review`
  and confirm it can call `query_node` via MCP (manual smoke test).

**Verification.**
- `uv run python scripts/generate_agents.py --check` exits 0.
- Diff: librarian/expert `.md` files have no `tools:` line;
  `cartographing-kitten.md` keeps its line.
- `mcp_tools:` field is absent from all `_source/agents/*.yaml` after the
  rewrite.

---

### Unit 4 — Strengthen `scripts/validate_skills.py` for Claude Code spec

**State:** complete

**Goal.** Encode the spec rules from Unit 1 into the validator so future
edits cannot regress.

**Requirements.** R1, R4.

**Dependencies.** Should land in the same PR as Unit 2; otherwise Unit 2's
fixed YAMLs will pass the old validator silently.

**Files.**
- `scripts/validate_skills.py`
- `tests/test_skill_validator.py`

**Approach.**

Add to `validate_skill`:
- Regex check: `frontmatter["name"]` must match `^[a-z0-9-]{1,64}$`.
- Length check: `frontmatter["description"]` ≤1024 chars (count after
  stripping the YAML literal block markers).
- Length check: `frontmatter.get("when_to_use", "")` ≤1024 chars.
- MCP prefix check: any `allowed-tools` entry starting with `mcp__` must
  match `mcp__plugin_kitty_kitty__` exactly. Mistyped prefixes (e.g.
  `mcp__kitty__`) fail.

Extend `KNOWN_TOOLS` with the namespaced forms of the existing MCP tools so
the prefix-version is recognized without relying on the `__` split fallback.

Add three tests to `tests/test_skill_validator.py`:
- `test_validates_name_format` — feeds a temp SKILL.md with `name:
  kitty:plan`, expects validation error.
- `test_validates_description_length` — feeds a 2,000-char description,
  expects error.
- `test_validates_mcp_prefix` — feeds `allowed-tools: [mcp__kitty__foo]`,
  expects error.

**Patterns to follow.** The existing tests use tmp_path fixtures and read
the validator's return list — mirror exactly.

**Test scenarios.**
- Happy path: existing valid skill YAMLs still pass after the new rules.
- Edge case: each new rule has a matching failing-case test.
- Error path: validator output includes the file path and a clear error
  string (not a Python traceback).

**Verification.**
- `uv run pytest tests/test_skill_validator.py -v` passes.
- `uv run python scripts/validate_skills.py` exits 0 against the post-Unit
  2 source tree.
- Pre-commit `kitty-validate-skills` passes.

---

### Unit 5 — Fix invalid agent color and add color validator

**State:** complete

**Goal.** A second-pass spec audit on 2026-05-15 surfaced one agent
(`librarian-kitten-flow`) declaring `color: magenta`. The Claude Code
subagents spec lists the accepted values as `red, blue, green, yellow,
purple, orange, pink, cyan` (https://code.claude.com/docs/en/sub-agents,
"Supported frontmatter fields"). `magenta` is silently ignored and the UI
falls back to a default, but the value is non-compliant.

**Requirements.** R1 (spec compliance for agent frontmatter), R4 (drift
protection).

**Files.**
- `plugins/kitty/_source/agents/librarian-kitten-flow.yaml`
- `plugins/kitty/agents/librarian-kitten-flow.md` (regenerated)
- `scripts/generate_agents.py` (new constant + loader check)
- `tests/test_generators.py` (two new tests)

**Approach.**
1. Change `color: magenta` to `color: pink` (closest visual analogue from
   the spec set; preserves the intent of distinguishing the flow agent from
   `expert-kitten-structure` which already uses `purple`).
2. In `scripts/generate_agents.py`, declare a module-level
   `VALID_AGENT_COLORS` frozenset matching the spec, and raise from
   `_load_agent_sources` when an agent declares an unrecognized color.
3. Add `test_all_agent_colors_match_claude_code_spec` and
   `test_agent_color_validator_rejects_unsupported_color` to
   `tests/test_generators.py`.
4. Regenerate: `uv run python scripts/generate_agents.py`.

**Verification.**
- `uv run pytest tests/test_generators.py -v` exits 0 with both new tests.
- `uv run python scripts/generate_agents.py --check` exits 0.

## System-Wide Impact

- **MCP server:** untouched.
- **Codex TOML output:** the Jinja template for Codex
  (`agent.codex.toml.j2`) does not reference `tools` or `mcp_tools`, so
  Codex output is unchanged.
- **CLAUDE.md sync:** Unit 1 adds one H2 in lockstep across CLAUDE.md and
  AGENTS.md; the sync checker will pass without allow-list changes.
- **Tests:** Unit 4 adds three tests; existing tests must continue passing
  (`uv run pytest`).

## Risks & Dependencies

- **Risk: Claude Code rejects the corrected `name:` fields differently than
  it rejected the colon-containing ones.** Mitigation: pre-commit smoke
  test by invoking `/kitty:kitty-plan` after regeneration. Fallback: if
  Claude Code's loader strictly requires `name` to match the directory,
  set `name: kitty-plan` (which the plan already does).
- **Risk: Removing `tools:` from agents grants them tools we did not
  intend (e.g. `Write` for a research agent).** Mitigation: research
  agents (`librarian-*`) already need to write to their handoff store via
  `add_litter_box_entry` / `add_treat_box_entry` MCP tools; review agents
  return JSON only and inherit `Write`/`Edit` but their developer
  instructions explicitly say "return JSON", so accidental edits are
  unlikely. If desired, a follow-up plan can add `disallowedTools:
  Write, Edit` to reviewers.
- **Risk: `KNOWN_TOOLS` enumeration drifts from the actual MCP server
  surface.** Mitigation: existing treat-box lesson #7 already documents
  this cross-cut. Optionally extend with a CI assert that
  `KNOWN_TOOLS ∩ mcp__plugin_kitty_kitty__*` matches the FastMCP tool
  registry — out of scope for this plan, but worth a follow-up.

## Sources & References

- [Claude Code Skills doc](https://code.claude.com/docs/en/skills)
- [Claude Code Subagents doc](https://code.claude.com/docs/en/sub-agents)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Anthropic skill-creator SKILL.md](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md)
- Repo: `scripts/validate_skills.py`, `scripts/generate_agents.py`,
  `scripts/generate_skills.py`,
  `plugins/kitty/_source/templates/agent.claude.md.j2`.
