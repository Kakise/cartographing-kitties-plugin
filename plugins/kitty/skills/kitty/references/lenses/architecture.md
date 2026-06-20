# Lens: architecture

The orchestrator injects this block into a `librarian-kitten` dispatch when the
research question is about how a codebase area is built — its technology stack,
module organization, key abstractions, and how layers connect.

> You are running the **architecture** lens. Read your one bundle section, then
> produce a structured research summary of the target area's architecture. Do
> not call MCP and do not explore the codebase; everything you need is in the
> bundle.

## What to look for

- **Technology & stack.** From the Target nodes and their roles/tags, identify
  the languages, frameworks, and key libraries present in the feature area.
- **Architecture & layers.** From the File structures, understand module
  organization — which files contain which abstractions and how they are
  grouped. Use roles to classify nodes by domain layer (e.g. "API handler",
  "data access", "business logic").
- **Relationships.** From the Key symbols section, map what imports what, what
  calls what, and what inherits from what. The 1-hop neighbor data shows how the
  central abstractions wire together.
- **Inputs & consumers.** From the Dependencies and Dependents sections,
  understand how the target area connects to the rest of the codebase — what it
  needs (upstream) and what relies on it (downstream).
- **Conventions.** Naming patterns, file organization, and test structure
  visible across the file structures.
- **Memory lessons.** Apply the litter-box risks and treat-box practices in the
  Memory lessons section to the area in scope.

## Coverage awareness

The bundle reflects current annotation coverage. When summaries/roles/tags are
sparse, lean on the structural data (kinds, edges, file layout) and on targeted
source-line reads to verify a claim, and flag reduced confidence in your output.
When coverage is high, trust the summaries and roles as the primary signal.

## What to report

- **Technology & stack** — languages, frameworks, key libraries detected.
- **Architecture** — module organization, layers, key abstractions.
- **Relevant patterns** — how similar features are implemented here.
- **Key files & symbols** — the most important nodes for the requested scope.
- **Dependencies & relationships** — how modules connect (imports, calls,
  inheritance).
- **Conventions** — naming patterns, file organization, test structure.
- **Memory lessons** — litter-box risks and treat-box practices relevant to the
  scope.

## Quality bar

- Prefer structural insights from the bundle over surface-level observations.
- Name specific files, classes, and functions — not vague descriptions.
- Use roles and tags to classify code by domain layer.
- Use the dependency/dependent data to explain how modules connect.
- Report what you found, not what you expected to find.

If a required piece of context is genuinely missing from your bundle section
(for example dependency or dependent data for a key symbol), return
`{status: 'needs_more_context'}` with the specific gap rather than guessing; the
orchestrator will enrich the bundle and re-dispatch you once. Otherwise return
`status: 'ok'` per `agent-output-contract.md`.
