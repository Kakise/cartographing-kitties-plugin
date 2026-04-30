---
title: Adopt AskUserQuestion as the question protocol for kitty skills
type: feat
status: complete
date: 2026-04-30
implemented_in: 4728969
---

## Overview

Standardize how every skill, command, and orchestrator in the kitty plugin asks the
user for clarification, decisions, and handoff choices. All interactive question
points must instruct the model to use Claude Code's `AskUserQuestion` tool with
structured multi-choice options instead of free-text prompts. Free-text fallback is
allowed only when the question is genuinely open-ended and no useful option set can
be derived from research.

Source of inspiration: <https://www.atcyrus.com/stories/claude-code-ask-user-question-tool-guide>.
The blog post emphasises a "model prompts you" pattern with targeted multi-choice
questions; we want the same UX everywhere the kitty skills currently say "ask the
user" or present numbered handoff menus.

## Problem Frame

Today the kitty skills ask the user in three different ways:

- Free-form prompts ("What problem are you trying to solve?") embedded in the
  SKILL.md instructions. The model usually replies with plain text, leaving the user
  to type prose answers.
- Numbered "Interactive mode" menus at the end of skills (1. … 2. … 3. …). The model
  surfaces these as markdown lists; the user must reply with text or numbers.
- Implicit "ask the user only when …" directions in `kitty:plan`'s Phase 2 (Resolve
  Questions) and `kitty:review`'s Stage 6 (Interactive). Behaviour depends on each
  invocation.

Claude Code now exposes the `AskUserQuestion` tool which renders multiple-choice
prompts with labels, descriptions, optional previews, and an automatic "Other" fallback.
It is the canonical way to gather user input mid-task. The plugin should:

- Replace numbered menus with `AskUserQuestion` calls.
- Convert "ask the user when …" directions into explicit `AskUserQuestion`
  invocations that include 2-4 options derived from research findings.
- Provide a single shared protocol document so each skill points to the same rules
  rather than re-stating the contract.
- Document the rule in `CLAUDE.md` so contributors keep it consistent.

## Requirements Trace

- **R1.** A single shared protocol describes when and how to use `AskUserQuestion`.
- **R2.** Every interactive question site in `kitty-brainstorm`, `kitty-plan`,
  `kitty-review`, and `kitty-work` instructs the model to use `AskUserQuestion`,
  with example questions/options.
- **R3.** Pipeline mode (`kitty:lfg` and similar non-interactive entry points)
  continues to skip user prompts.
- **R4.** The router `kitty` skill and the project `CLAUDE.md` document the
  convention so future skills inherit it.
- **R5.** Skill validation (`scripts/validate_skills.py`) and the existing
  pre-commit / lint suite still pass after the edits.
- **R6.** The skills submodule (`Kakise/cartographing-kitties-skills`) carries the
  source-of-truth changes; the parent repo updates the submodule pointer in the
  same change set.

## Scope Boundaries

**In scope**
- Editing SKILL.md files inside `plugins/kitty/skills/` (the skills submodule).
- Adding `plugins/kitty/skills/kitty/references/ask-user-protocol.md`.
- Documenting the convention in `CLAUDE.md`.
- Updating the parent repo's submodule pointer.

**Out of scope**
- Changing MCP server / Python source code. `AskUserQuestion` is a Claude Code
  harness tool; the MCP server does not need to know about it.
- Adding a new MCP tool or wrapper. We use the harness tool directly.
- Modifying agents under `plugins/kitty/agents/`. Worker agents do not have
  `AskUserQuestion` in their tool list and must not ask the user; they return
  results to the orchestrator skill.
- Touching `kitty-explore`, `kitty-impact`, `kitty-annotate`, or `kitty:lfg`
  workflows beyond cross-references — they have no interactive question sites.

## Memory Context

- **Litter lessons to avoid:** Memory boxes are empty. No prior negative lessons
  recorded.
- **Treat lessons to follow:** Memory boxes are empty. No prior validated patterns
  recorded.
- **Memory gaps:** No relevant entries for "question", "user input", or "skill"
  searches. Must rely on existing CLAUDE.md conventions and the inline-first
  workflow contract documented in `docs/architecture/codex-workflow-contract.md`.

## Context & Research

### Skill audit (where questions are asked today)

| Skill | Section | Today | Replace with |
|---|---|---|---|
| `kitty-brainstorm` | Phase 1.3 (no args) | "ask: What problem are you trying to solve?" | `AskUserQuestion` only when 2-4 plausible options can be inferred; otherwise keep free-form prompt and note it as the documented exception |
| `kitty-brainstorm` | Phase 3 Adaptive Questioning | 4 question categories asked one at a time as text | `AskUserQuestion` with options derived from research findings |
| `kitty-brainstorm` | Phase 5 Handoff Interactive | numbered menu (3 items) | `AskUserQuestion` (single-select, 3 options) |
| `kitty-plan` | Phase 0 (resume) | inline "offer to resume if found" | `AskUserQuestion` (resume / start fresh / view) when matches exist |
| `kitty-plan` | Phase 2 Resolve Questions | "Ask the user only when the answer materially affects …" (free-form) | `AskUserQuestion` for each material decision; defer or skip otherwise |
| `kitty-plan` | Phase 6 Handoff Interactive | numbered menu (3 items) | `AskUserQuestion` (single-select, 3 options) |
| `kitty-review` | Stage 6 Interactive | "For each P0/P1, ask: fix now, defer, or dismiss?" | `AskUserQuestion` (single-select; or batched multiSelect when 4+ findings) |
| `kitty-work` | Phase 1.4 branch isolation | "when the user wants branch isolation" | `AskUserQuestion` (current branch / new branch / new worktree) when on main without explicit instruction |
| `kitty-work` | Phase 4.6 commit | "Commit … when the user wants" | `AskUserQuestion` (commit now / squash later / leave staged) when uncommitted work exists at end of phase |

### Out-of-scope question sites (no change)

- `kitty-annotate`, `kitty-explore`, `kitty-impact`: no user questions today.
- `kitty:lfg`: pipeline mode skips interactive prompts. No change beyond
  cross-reference.
- Agents under `plugins/kitty/agents/`: worker agents return JSON or structured
  text. They do not interact with the user.

### Submodule realities

`plugins/kitty/skills/` is a git submodule pinned at
`Kakise/cartographing-kitties-skills@a4ac3f9`. Edits inside the submodule must be
committed against that submodule, then the parent repo updates the submodule
pointer (the commit SHA in `.gitmodules`-tracked tree). The plan's working units
spell this out.

### AskUserQuestion contract (from blog post + tool schema)

- 1-4 questions per call, each with 2-4 options (excluding the auto-added "Other").
- Each option has a `label` (1-5 words) and `description` (one sentence).
- Optional `header` chip text (≤ 12 chars).
- Optional `preview` for side-by-side comparison (single-select only).
- Optional `multiSelect: true` for non-mutually-exclusive choices.
- Recommended option, when one exists, goes first and is suffixed `(Recommended)`.
- Pipeline / autonomous flows must NOT call `AskUserQuestion`.

## Key Technical Decisions

1. **Single shared reference document.** Add
   `plugins/kitty/skills/kitty/references/ask-user-protocol.md`. Each affected
   SKILL.md links to it from its question-site sections rather than restating the
   rules. Mirrors the existing pattern of `memory-workflow.md` and
   `subgraph-context-format.md`.

2. **Keep "Pipeline mode" gate explicit.** Every question site keeps an explicit
   "Pipeline mode: skip the question" sentence so `kitty:lfg` orchestration still
   works without prompts.

3. **Recommended-option convention.** When research strongly suggests one path
   (e.g., the recommended handoff after `kitty:plan` finishes is `kitty:work`),
   put it first and append `(Recommended)` to the label per Claude Code guidance.

4. **Free-form fallback rule.** If a question genuinely has no enumerable answer
   (e.g., "describe the feature you want"), the SKILL.md tells the model to keep
   asking in plain text and to call `AskUserQuestion` for any follow-up
   refinement that admits options. This mirrors the spec-based interview pattern
   from the blog post.

5. **Per-finding vs. batched review prompts.** `kitty-review` Stage 6 uses
   per-finding `AskUserQuestion` for P0 (one decision per critical issue) and a
   single `multiSelect` `AskUserQuestion` to triage P1+ (e.g., "Which findings to
   fix now?"). Keeps prompt count bounded.

6. **Submodule-first edits.** All SKILL edits land in
   `plugins/kitty/skills/` (submodule working tree) and are committed in the
   submodule. The final unit bumps the submodule pointer in the parent repo.

## Open Questions

None blocking. All design choices above are derivable from the blog post and the
existing skill contracts.

## Implementation Units

### Unit 1 — Add the shared AskUserQuestion protocol reference

**State:** complete
- **Goal:** Provide a single document every skill links to so the rules are not
  re-stated in five places.
- **Requirements:** R1, R3
- **Dependencies:** none
- **Files:**
  - `plugins/kitty/skills/kitty/references/ask-user-protocol.md` (new, in submodule)
- **Approach:**
  - Document when to call `AskUserQuestion`: handoff menus, blocking
    clarifications, decision points where 2-4 enumerable options exist.
  - Document when NOT to call it: pipeline mode, free-form description requests,
    questions to worker agents, internal reasoning prompts.
  - Include parameter cheatsheet (questions, options, header limits, multiSelect,
    preview, recommended-option convention).
  - Include 3 worked examples mirroring the blog post: brainstorm scope question,
    plan handoff, review per-finding triage.
  - Include "Pipeline mode" rule: when invoked from `kitty:lfg` or any
    non-interactive driver, the model must skip the prompt and choose the
    recommended option silently.
- **Patterns to follow:** mimic the structure of
  `plugins/kitty/skills/kitty/references/memory-workflow.md` (purpose / preflight /
  applying / postflight / output contract).
- **Test scenarios:**
  - Happy path: file exists; markdown lints clean; `scripts/validate_skills.py`
    passes (it scans for malformed front-matter / missing references).
  - Edge case: relative-link check — every other SKILL.md that links to it can
    resolve the path.
- **Verification:** Run `uv run python scripts/validate_skills.py` after the
  unit. File present, links resolve, markdown is clean.

### Unit 2 — Update `kitty-brainstorm` question sites

**State:** complete
- **Goal:** Replace adaptive-questioning prose and the handoff menu with
  `AskUserQuestion` instructions; preserve the spec-style interview pattern.
- **Requirements:** R2, R3
- **Dependencies:** Unit 1
- **Files:**
  - `plugins/kitty/skills/kitty-brainstorm/SKILL.md`
- **Approach:**
  - Phase 1.3 (no arguments): leave as free-form prompt with a note that
    follow-up refinement should use `AskUserQuestion`.
  - Phase 3 Adaptive Questioning: rewrite the four question categories so each
    instructs the model to call `AskUserQuestion` with options derived from
    research findings. Provide one worked example using research output ("the
    repo uses X pattern; should this feature follow X or propose Y?").
  - Phase 5 Handoff: replace the numbered menu with an `AskUserQuestion` call
    (single-select, 3 options, recommended option first).
  - Add a "See also: kitty/references/ask-user-protocol.md" line where relevant.
  - Preserve "Pipeline mode" gates explicitly.
- **Patterns to follow:** existing memory-workflow link style at the top of the
  Phase sections.
- **Test scenarios:**
  - Happy path: dry-run the skill mentally — every interactive prompt now has an
    explicit AskUserQuestion instruction with at least 2 options.
  - Edge case: pipeline mode lines remain.
  - Integration: front-matter unchanged; description matches the source repo's
    SKILL.md template (validated by `scripts/validate_skills.py`).
- **Verification:** `scripts/validate_skills.py` clean; manual diff review shows
  no remaining numbered handoff menus or "ask: …" prose in question sites.

### Unit 3 — Update `kitty-plan` question sites

**State:** complete
- **Goal:** Convert resume-offer, Resolve-Questions, and handoff menus to
  `AskUserQuestion`.
- **Requirements:** R2, R3
- **Dependencies:** Unit 1
- **Files:**
  - `plugins/kitty/skills/kitty-plan/SKILL.md`
- **Approach:**
  - Phase 0.1 (resume): when `docs/plans/` matches exist, instruct
    `AskUserQuestion` with options "Resume `<plan>`", "Start fresh", "Open in
    editor first". Recommended option = Resume.
  - Phase 2 Resolve Questions: rewrite as: build the question list from research;
    for each material decision, call `AskUserQuestion` with 2-4 options derived
    from the research findings. Defer non-material questions to the plan body.
  - Phase 6 Handoff: replace the numbered menu with `AskUserQuestion`
    (single-select). Recommended = `kitty:work` for active plans.
  - Reference `kitty/references/ask-user-protocol.md`.
  - Preserve all Pipeline mode gates.
- **Test scenarios:**
  - Happy path: every interactive prompt is an `AskUserQuestion` instruction.
  - Edge case: when no resume candidates exist, the resume question is not asked.
  - Integration: front-matter unchanged; lints pass.
- **Verification:** `scripts/validate_skills.py` clean; grep for legacy patterns
  ("Interactive mode:.*Present options", "1\.", "2\.", "3\.") shows none in the
  Phase sections.

### Unit 4 — Update `kitty-review` Stage 6 triage

**State:** complete
- **Goal:** Use `AskUserQuestion` for fix/defer/dismiss decisions; keep autofix
  and report-only modes silent.
- **Requirements:** R2, R3
- **Dependencies:** Unit 1
- **Files:**
  - `plugins/kitty/skills/kitty-review/SKILL.md`
- **Approach:**
  - Stage 6 Interactive: per P0 finding, call `AskUserQuestion` with options
    "Fix now", "Defer (keep in report)", "Dismiss". Recommended = "Fix now".
  - For 4+ P1/P2 findings, use a single `multiSelect: true` `AskUserQuestion`:
    "Which findings should we fix now?". Each option = `severity` + truncated
    issue label. Limit to 4 options at a time; loop if needed.
  - Autofix mode: still no user interaction.
  - Report-only mode: still no user interaction.
  - Reference the protocol doc.
- **Test scenarios:**
  - Happy path: interactive mode now drives a tool call per critical finding and
    a batched call for the long tail.
  - Edge case: 0 findings → no prompt fired.
  - Edge case: autofix and report-only modes have explicit "do not call
    AskUserQuestion" notes.
- **Verification:** `scripts/validate_skills.py` clean; mode descriptions still
  match the table at the top of the SKILL.md.

### Unit 5 — Update `kitty-work` decision points

**State:** complete
- **Goal:** Replace implicit "when the user wants …" branches with explicit
  `AskUserQuestion` prompts for branch isolation and end-of-phase commit.
- **Requirements:** R2, R3
- **Dependencies:** Unit 1
- **Files:**
  - `plugins/kitty/skills/kitty-work/SKILL.md`
- **Approach:**
  - Phase 1.4 (branch isolation): when on `main` or another protected branch and
    the invoking user has not specified, call `AskUserQuestion` with options
    "Stay on current branch", "Create feature branch (Recommended)", "Create
    worktree". Skip prompt in pipeline mode (use Recommended).
  - Phase 4.6 (commit): when uncommitted changes exist at end of phase and the
    user has not specified, call `AskUserQuestion` with options "Commit now",
    "Stage for review", "Leave dirty". Skip in pipeline mode (use plan default
    or Recommended).
  - Add a note that Phase 4.7 (push/PR) keeps requiring explicit user request;
    no automatic prompt.
  - Reference the protocol doc.
- **Test scenarios:**
  - Happy path: a branch question fires when on `main` without explicit
    instruction.
  - Edge case: pipeline mode skips both prompts.
  - Edge case: when the user already specified branch/commit behaviour, skip the
    prompt.
- **Verification:** `scripts/validate_skills.py` clean; SKILL.md still under the
  CodexCLI tool list constraints documented in the workflow contract.

### Unit 6 — Document the convention in router skill and CLAUDE.md

**State:** complete
- **Goal:** Make the AskUserQuestion convention discoverable for contributors and
  future skills.
- **Requirements:** R1, R4
- **Dependencies:** Unit 1
- **Files:**
  - `plugins/kitty/skills/kitty/SKILL.md` (add a one-paragraph "Asking the
    user" section pointing at the protocol doc, in the submodule)
  - `CLAUDE.md` (add a Conventions bullet that all interactive prompts use
    `AskUserQuestion`)
- **Approach:**
  - Router skill: add a short subsection under "Tips" or "Key conventions" with
    a one-line summary and a link to
    `kitty/references/ask-user-protocol.md`.
  - `CLAUDE.md`: add a bullet under "Conventions": "Skills ask the user via
    Claude Code's `AskUserQuestion` tool whenever 2-4 enumerable options exist;
    pipeline mode skips prompts. See `plugins/kitty/skills/kitty/references/ask-user-protocol.md`."
- **Test scenarios:**
  - Happy path: pre-commit hooks (codespell, markdown checks) pass.
  - Edge case: contributors searching for "ask" in CLAUDE.md find the rule.
- **Verification:** `uv run pre-commit run --all-files` succeeds.

### Unit 7 — Submodule + parent repo wiring

**State:** complete — implemented in 4728969 (parent) bumping submodule to `Kakise/cartographing-kitties-skills@2dfaed3`
- **Goal:** Land the skill edits in the submodule and update the parent pointer
  consistently.
- **Requirements:** R5, R6
- **Dependencies:** Units 1-6
- **Files:**
  - `plugins/kitty/skills/` (submodule pointer in parent repo)
  - Submodule branch: `feat/ask-user-protocol` in
    `Kakise/cartographing-kitties-skills`.
- **Approach:**
  - Inside `plugins/kitty/skills`, create a feature branch, commit Units 1-6's
    skill edits, push to fork, open PR (only when explicitly requested or when
    the surrounding workflow guarantees it; otherwise leave the branch local).
  - In the parent repo, update the submodule reference to the new commit, run
    `uv run pre-commit run --all-files`, and commit the bump.
  - Verify `git submodule status` shows clean checkout pointing at the new SHA.
- **Test scenarios:**
  - Happy path: submodule + parent commits align; pre-commit passes.
  - Edge case: if pre-commit reformat changes any file, re-stage and amend the
    submodule commit before bumping the parent (do not amend after the parent
    pointer has been pushed).
- **Verification:** `git submodule status` clean; `uv run pre-commit run
  --all-files` succeeds in the parent.

## System-Wide Impact

- No runtime behaviour change for the MCP server, indexing pipeline, or graph
  storage layer.
- Claude Code (and any other harness exposing `AskUserQuestion`) renders the new
  prompts. Harnesses that do not expose `AskUserQuestion` will follow the
  free-form fallback the protocol document describes.
- Existing tests, lint, and typecheck remain green: only Markdown content changes.

## Risks & Dependencies

- **Harness compatibility.** Harnesses other than Claude Code may not expose
  `AskUserQuestion`. Mitigation: protocol doc explicitly states "if the tool is
  unavailable, fall back to a numbered free-form question and continue". Codex
  inline-first contract is preserved (no behaviour change since Codex skills are
  inline-first today).
- **Submodule drift.** The submodule must land first; otherwise the parent
  pointer bump references a non-existent commit. Mitigation: Unit 7 enforces the
  ordering.
- **Pipeline mode regressions.** If we forget a "Pipeline mode" gate on a new
  prompt, `kitty:lfg` could block. Mitigation: every Unit 2-5 explicitly checks
  the gate is present.
- **Validate-skills false negatives.** `scripts/validate_skills.py` does not yet
  inspect for AskUserQuestion adoption. Out of scope to extend it; rely on
  reviewer/test verification.

## Sources & References

- AtCyrus blog post: <https://www.atcyrus.com/stories/claude-code-ask-user-question-tool-guide>
- `plugins/kitty/skills/kitty/references/memory-workflow.md` — pattern reference
- `plugins/kitty/skills/kitty-brainstorm/SKILL.md` — Phase 3, Phase 5
- `plugins/kitty/skills/kitty-plan/SKILL.md` — Phase 0, Phase 2, Phase 6
- `plugins/kitty/skills/kitty-review/SKILL.md` — Stage 6
- `plugins/kitty/skills/kitty-work/SKILL.md` — Phase 1, Phase 4
- `docs/architecture/codex-workflow-contract.md` — inline-first guarantees
- `docs/architecture/repo-boundaries.md` — submodule edit policy