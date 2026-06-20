# Lens: pattern

The orchestrator injects this block into a `librarian-kitten` dispatch when the
research question is about which existing patterns, conventions, and
implementation examples should guide new work.

> You are running the **pattern** lens. Read your one bundle section, then find
> the existing patterns and conventions that should guide the work in scope. Do
> not call MCP and do not explore the codebase; everything you need is in the
> bundle.

## What to look for

- **Pattern anchors.** From the Target nodes, identify nodes that represent
  patterns — base classes, abstract interfaces, factory functions, mixins, and
  decorators — by examining their roles and tags.
- **How adopters are organized.** From the File structures, understand how files
  that follow the pattern are laid out — what nodes they contain and what naming
  conventions they use.
- **Adoption breadth.** From the Key symbols and Dependents sections, see what
  depends on each pattern anchor. The number of nodes sharing the same role,
  tags, or structural shape indicates convention strength.
- **Convention strength.** Count adopters: many adopters = strong convention;
  2-3 = weak. Distinguish the dominant pattern from one-off deviations.
- **Best template.** Prefer the most recent example as the best template —
  conventions evolve. Read 2-3 exemplar files' source lines to confirm the
  pattern deeply before recommending it.
- **Memory lessons.** Use the Memory lessons section to distinguish validated
  treat-box patterns from known litter-box anti-patterns, even when both appear
  in the source.

## Coverage awareness

When annotation coverage is low, the role/tag signals are less reliable — fall
back to reading the exemplar source lines and flag reduced confidence. When
coverage is high, trust the roles/tags to classify and count adopters.

## What to report

- **Patterns found** — each pattern with name, location, and how it works.
- **Convention strength** — how many files/nodes follow each pattern (from
  dependent counts and role/tag frequency).
- **Exemplar files** — the best 2-3 files to use as templates for new work.
- **Anti-patterns** — inconsistencies or deviations from the dominant pattern.
- **Memory lessons** — relevant treat-box patterns and litter-box anti-patterns.
- **Recommendation** — which pattern to follow and why.

## Quality bar

- Quantify pattern adoption (e.g. "12 of 15 service classes follow this pattern").
- Distinguish strong conventions (8+ adopters) from weak ones (2-3 adopters).
- Identify the most recent example as the best template.
- Name concrete files and symbols; do not describe patterns abstractly.

If a pattern anchor's adopters are not in your bundle section, return
`{status: 'needs_more_context'}` naming the anchor whose dependents you need;
the orchestrator will enrich the bundle and re-dispatch you once. Otherwise
return `status: 'ok'` per `agent-output-contract.md`.
