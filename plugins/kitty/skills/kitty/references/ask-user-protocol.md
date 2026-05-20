# AskUserQuestion Protocol

This is the canonical contract for **how kitty skills ask the user a question**.
Every interactive prompt site in the kitty skills must follow this protocol so that
clarifications, decisions, and handoff menus look and feel the same across the
plugin.

The protocol exists because Claude Code now ships a first-class
[`AskUserQuestion`](https://www.atcyrus.com/stories/claude-code-ask-user-question-tool-guide)
tool that renders multiple-choice prompts with labels, descriptions, optional
previews, and an automatic "Other" fallback. Free-form prompts like
*"What problem are you trying to solve?"* and numbered handoff menus like
*"1. Open in editor   2. Continue refining"* are no longer the right surface; they
become `AskUserQuestion` calls.

## Purpose

- **Make decisions structured.** Multi-choice prompts with descriptions are easier
  to compare than prose, and they preserve the model's recommendation.
- **Make non-interactive runs safe.** Pipeline orchestrators (`kitty:lfg`, the
  `mode:autofix` and `mode:report-only` review modes, anything driven by
  CronCreate / RemoteTrigger / autonomous loops) skip the prompt and pick the
  recommended option silently.
- **Keep the contract uniform.** Skills do not re-state these rules; they link
  to this document.

## When to call `AskUserQuestion`

Use it whenever **all** of these hold:

1. The skill is in interactive mode (no `mode:autofix`, no `mode:report-only`,
   not invoked as part of `kitty:lfg`, not driven by an autonomous loop).
2. The decision materially affects scope, architecture, blast radius, or which
   skill runs next.
3. You can describe **2-4 enumerable options** for the user, each with a clear
   label and one-sentence description. (Claude Code adds an "Other" option
   automatically; do not add one yourself.)

## When NOT to call `AskUserQuestion`

Skip it for:

- **Pipeline mode.** Treat the recommended option as the answer and continue
  silently. Every question site in the kitty skills carries an explicit
  *"Pipeline mode: skip this prompt"* gate; honour it.
- **Free-form descriptions.** *"Describe the feature you want"* has no enumerable
  answer. Ask in plain text and call `AskUserQuestion` for any follow-up
  refinement that admits options. This mirrors the spec-based interview pattern
  from the source blog post: open the conversation broadly, then narrow with
  targeted multi-choice prompts.
- **Worker / reviewer agents.** Framework subagents under
  `plugins/kitty/agents/` do not have `AskUserQuestion` in their tool list and
  must not address the user; they return structured results to the orchestrator
  skill.
- **Internal reasoning.** Do not use `AskUserQuestion` to plan or to "check with
  yourself". It is for user input only.
- **Plan approval flows.** If you need plan approval, exit plan mode the normal
  way; do not pose *"Is the plan good?"* as an `AskUserQuestion`.

## How to call `AskUserQuestion`

### Parameter cheatsheet

| Field | Required | Notes |
|---|---|---|
| `question` | yes | Full question, ends with `?`. Phrase as *"Which …?"* / *"How should we …?"* / *"What should happen when …?"*. If `multiSelect` is `true`, phrase it accordingly: *"Which findings should we fix now?"*. |
| `header` | yes | ≤ 12 characters, used as a chip/tag on the prompt. Examples: *"Auth method"*, *"Library"*, *"Approach"*. |
| `options` | yes | 2-4 entries. Each has `label` (1-5 words) and `description` (one sentence on what choosing it means). Do NOT include an "Other" option — Claude Code adds it automatically. |
| `multiSelect` | yes | `false` for single-choice (default). `true` only when the choices are not mutually exclusive — e.g., "Which findings to fix?". |
| `preview` | no | Use ONLY for single-select questions where the user benefits from side-by-side ASCII / code / config comparison (UI mockups, alternative implementations, diagrams). Do NOT use for simple preference questions where label + description suffice. |

### Recommended-option convention

When research strongly suggests one path, put it first and append `(Recommended)`
to the label:

```text
options:
  - label: "Run kitty:work (Recommended)"
    description: "Start implementing the plan immediately."
  - label: "Run kitty:review on the plan"
    description: "Pre-flight the plan with the reviewer agents before coding."
  - label: "Open the plan in the editor"
    description: "Read or refine the plan locally before continuing."
```

### Maximum prompts per call

Each `AskUserQuestion` call accepts 1-4 questions. Group related decisions when
they will be answered together. Otherwise prefer one prompt per decision so the
user's answer to question A can shape question B.

## Worked examples

### Brainstorm — scope question derived from research

```yaml
question: "Should this feature follow the existing event-bus pattern in `src/cartograph/server/events.py`, or introduce a new pub/sub layer?"
header: "Pattern"
multiSelect: false
options:
  - label: "Reuse event-bus (Recommended)"
    description: "Extend the existing pattern; lowest churn."
  - label: "New pub/sub layer"
    description: "Introduce a dedicated module; more decoupling, more code."
  - label: "Synchronous calls"
    description: "Skip eventing; call directly. Easiest if there is only one consumer."
```

The model derives the options from `librarian-kitten-pattern` findings; it does
not invent them.

### Plan handoff — single-select menu

```yaml
question: "What would you like to do next with this plan?"
header: "Plan handoff"
multiSelect: false
options:
  - label: "Run kitty:work (Recommended)"
    description: "Start implementing the plan immediately."
  - label: "Run kitty:review on the plan"
    description: "Pre-flight the plan with the reviewer agents."
  - label: "Open the plan in the editor"
    description: "Read or refine the plan locally before continuing."
```

### Review — per-finding triage

```yaml
question: "Finding [P0] in src/foo.py:42 — null-deref when `user.email` is None. How should we handle it?"
header: "P0 finding"
multiSelect: false
options:
  - label: "Fix now (Recommended)"
    description: "Apply the suggested fix and re-run tests."
  - label: "Defer (keep in report)"
    description: "Leave the finding in the review artifact; do not edit code."
  - label: "Dismiss"
    description: "Mark as not-a-bug; suppress in future reports."
```

### Review — batched P1+ triage

```yaml
question: "Which P1/P2 findings should we fix now?"
header: "Triage"
multiSelect: true
options:
  - label: "[P1] missing test for save_user"
    description: "src/users.py — add coverage for the rename path."
  - label: "[P1] inconsistent error type"
    description: "src/api.py — RaiseError vs HttpError mismatch."
  - label: "[P2] dead helper `_legacy_decode`"
    description: "src/utils.py — unused after refactor."
  - label: "[P2] outdated comment in router"
    description: "src/router.py — comment references removed flag."
```

If there are more than four findings to triage, batch four at a time and loop.

## Pipeline-mode behaviour

When the active workflow is non-interactive (`kitty:lfg`, `mode:autofix`,
`mode:report-only`, autonomous loops driven by `CronCreate`, `RemoteTrigger`,
or any orchestrator that promises silent execution), the model must:

- Skip the `AskUserQuestion` call entirely.
- Pick the option marked `(Recommended)` and continue.
- Note the implicit choice in the final output (so the user can audit later).

If the recommended option is unsafe in the current context (e.g., recommended is
"Commit now" but tests are failing), fall back to the safest non-destructive
option and record the reason in the output.

## Harness fallback

If the runtime does not expose `AskUserQuestion` (e.g., a Codex inline-first
session, a CLI replay), the model may fall back to a numbered free-form question
mirroring the same options. The skill must still skip the prompt in pipeline
mode.

## Output Contract

Every workflow that uses this protocol should mention prompts in its final
output:

- Number of `AskUserQuestion` calls fired.
- Decisions taken (option labels chosen).
- Pipeline-mode auto-choices (option labels picked silently and the reason).

This makes it easy to audit interactive vs autonomous runs after the fact.