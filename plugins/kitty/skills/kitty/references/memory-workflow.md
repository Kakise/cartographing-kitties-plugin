# Memory Workflow

The litter box and treat box are persistent workflow memory. They are not status
dashboards; planning, work, and review workflows must actively consult them.

## Purpose

- **Litter box:** negative lessons. Failures, regressions, unsupported approaches,
  anti-patterns, and things to never repeat.
- **Treat box:** positive lessons. Validated patterns, conventions, optimizations,
  best practices, and things to always do.

## Preflight Protocol

Before planning, implementing, or reviewing:

1. Extract 2-4 search terms from the request, plan, changed files, or target symbols.
2. Call `query_litter_box` once with no filters to get recent negative lessons.
3. Call `query_treat_box` once with no filters to get recent positive lessons.
4. If there are obvious domain terms, call filtered queries with `search=<term>` for
   the strongest 1-2 terms.
5. Add a `### Memory Context` section to the subgraph context or plan:
   - Litter lessons to avoid
   - Treat lessons to follow
   - Any memory gaps, when both boxes return no relevant entries

If memory tools are unavailable, state that explicitly and continue. Do not silently
skip memory.

## Applying Memory

- Plans must convert relevant treat-box entries into `Patterns to follow` or
  `Key Technical Decisions`.
- Plans must convert relevant litter-box entries into `Risks & Dependencies` or
  explicit non-goals.
- Work must check litter-box entries before implementing risky areas and must follow
  relevant treat-box conventions unless current source proves they are obsolete.
- Review must treat repeated litter-box failures as higher confidence findings and
  use treat-box entries as the local convention baseline.

## Postflight Protocol

After work or review:

1. Add a litter-box entry when a failure, regression, flaky behavior, unsupported
   approach, or repeated anti-pattern was discovered by calling `add_litter_box_entry`.
2. Add a treat-box entry when a pattern was validated by implementation, tests, or
   review and is likely to help future sessions by calling `add_treat_box_entry`.
3. Keep entries reusable:
   - Description: one specific lesson, not a transcript.
   - Context: file paths, symbols, test names, plan path, or error text.
   - Source agent: skill or agent name, such as `kitty:work` or
     `expert-kitten-testing`.

Do not record low-confidence guesses. If a lesson is useful only for the current
conversation, leave it in the final response instead of persistent memory.

## Categories

Litter categories:
- `failure`
- `anti-pattern`
- `unsupported`
- `regression`
- `never-do`

Treat categories:
- `best-practice`
- `validated-pattern`
- `always-do`
- `convention`
- `optimization`

## Output Contract

Every workflow that uses this protocol should mention memory in its final output:

- Queried memory: yes/no
- Applied lessons: count or brief list
- Recorded new lessons: count, or `none`
