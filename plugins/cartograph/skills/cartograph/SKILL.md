---
name: cartograph
description: >
  Use Cartograph MCP tools for structural codebase intelligence — dependency mapping,
  impact analysis, code exploration, refactoring planning, and semantic search via
  LLM-annotated summaries. Trigger this skill whenever the user asks about codebase
  structure, what depends on something, what a module contains, how files relate,
  impact of a change, dependency graphs, or anything that benefits from understanding
  code relationships rather than just text search. Also use when the user asks to
  explore, navigate, understand, or analyze a codebase — even informally like "what's
  in this project?" or "how is this organized?". Cartograph parses code with tree-sitter,
  stores relationships in a SQLite graph, and supports agent-driven annotation.
  Prefer Cartograph over grep/glob for structural and relational questions.
---

# Cartograph — Codebase Intelligence

Cartograph gives you a graph-based mental model of the codebase. It knows about
functions, classes, modules, imports, calls, and inheritance — not just text matches.

## When Cartograph beats grep/glob

| You need... | Use |
|---|---|
| What imports/calls/inherits X? | Cartograph (`find_dependents`, `query_node`) |
| What does X depend on? | Cartograph (`find_dependencies`) |
| What's in this file and how does it connect? | Cartograph (`get_file_structure`) |
| What breaks if I change Y? | Cartograph (`find_dependents`) |
| Code by concept/domain ("authentication", "payment") | Cartograph (`search`) — after annotation |
| A specific string/pattern/TODO | grep/glob |

## Decision heuristic

When you get a request, follow this mental model and delegate to the appropriate sub-skill:

1. **Structural/relational question?** (definitions, imports, call chains, file contents, class hierarchy)
   → Use **`cartograph:explore`** — start with `query_node` or `get_file_structure`.

2. **Planning a change?** (blast radius, what breaks, dependency analysis)
   → Use **`cartograph:impact`** — start with `find_dependents`.

3. **Semantic/domain question?** ("find all auth code", "what handles payments?")
   → Check `annotation_status`. If many nodes are pending, use **`cartograph:annotate`**
   first, then `search`.

4. **Plain text search?** (string literal, error message, TODO)
   → Fall back to grep/glob. Cartograph isn't a text search engine.

## Tool skills

| Sub-skill | Purpose |
|---|---|
| `cartograph:explore` | Structural exploration — browse definitions, imports, relationships |
| `cartograph:impact` | Impact analysis — blast radius, dependency chains, refactor planning |
| `cartograph:annotate` | Enrich graph with summaries and tags for semantic search |

## Workflow skills

Full engineering pipeline powered by Cartograph agent swarms:

| Skill | Purpose |
|---|---|
| `cartograph:brainstorm` | Requirements gathering with Cartograph-powered research swarms |
| `cartograph:plan` | Technical planning with parallel research agents for deep codebase understanding |
| `cartograph:work` | Execute plans with Cartograph-first worker swarms |
| `cartograph:review` | Multi-agent code review with structural impact analysis |
| `cartograph:lfg` | Full autonomous pipeline: plan → work → review (no interaction needed) |

Pipeline: `cartograph:brainstorm` → `cartograph:plan` → `cartograph:work` → `cartograph:review`

Or use `cartograph:lfg` to run plan → work → review autonomously.

## Quick start

1. **First use or stale index** → call `index_codebase(full=false)` for incremental, `full=true` for full reindex
2. **Explore structure** → use `cartograph:explore`
3. **Assess change impact** → use `cartograph:impact`
4. **Enable semantic search** → use `cartograph:annotate`
5. **Build a feature** → use `cartograph:lfg "feature description"` for full autonomous pipeline

## Key conventions

- **Qualified names** use `::` separator: `module.path::ClassName::method_name`
- **Edge kinds** for filtering: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- **Node kinds**: `module`, `class`, `function`, `method`, `variable`
- The graph lives in `.cartograph/graph.db` inside the project root
- Indexing is incremental by default — only changed files are re-parsed

## MCP Prompts

The server also exposes guided workflow prompts that MCP clients can invoke directly:

| Prompt | Purpose |
|---|---|
| `explore_codebase(focus?)` | Step-by-step codebase exploration guidance |
| `plan_refactor(target)` | Guided refactoring with blast radius analysis |
| `annotate_batch(batch_size?)` | Batch annotation workflow guidance |

## Tips

- Run `index_codebase` at conversation start if you're unsure about freshness
- Combine sub-skills: explore first, then assess impact before changing code
- For large codebases (50+ pending nodes), `cartograph:annotate` supports parallel subagents
- See `references/tool-reference.md` for full tool parameter details
