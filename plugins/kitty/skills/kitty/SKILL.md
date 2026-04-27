---
name: kitty
description: >
  Use Cartographing Kittens MCP tools for structural codebase intelligence — dependency mapping,
  impact analysis, code exploration, refactoring planning, and semantic search via
  LLM-annotated summaries. Trigger this skill whenever the user asks about codebase
  structure, what depends on something, what a module contains, how files relate,
  impact of a change, dependency graphs, or anything that benefits from understanding
  code relationships rather than just text search. Also use when the user asks to
  explore, navigate, understand, or analyze a codebase — even informally like "what's
  in this project?" or "how is this organized?". Cartographing Kittens parses code with tree-sitter,
  stores relationships in a SQLite graph, and supports agent-driven annotation.
  Prefer Cartographing Kittens over grep/glob for structural and relational questions.
---

# Cartographing Kittens — Codebase Intelligence

Cartographing Kittens gives you a graph-based mental model of the codebase. It knows about
functions, classes, modules, imports, calls, and inheritance — not just text matches.

## When Cartographing Kittens beats grep/glob

| You need... | Use |
|---|---|
| What imports/calls/inherits X? | Cartographing Kittens (`find_dependents`, `query_node`) |
| What does X depend on? | Cartographing Kittens (`find_dependencies`) |
| What's in this file and how does it connect? | Cartographing Kittens (`get_file_structure`) |
| Token-efficient overview of multiple files | Cartographing Kittens (`get_context_summary`) |
| Look up multiple symbols at once | Cartographing Kittens (`batch_query_nodes`) |
| What breaks if I change Y? | Cartographing Kittens (`find_dependents`) |
| What's most important in this area? | Cartographing Kittens (`rank_nodes`) |
| Structural diff after changes | Cartographing Kittens (`graph_diff`) |
| Structural health checks | Cartographing Kittens (`validate_graph`) |
| Stale annotations after code changes | Cartographing Kittens (`find_stale_annotations`) |
| Durable workflow lessons | Cartographing Kittens (`query_litter_box`, `query_treat_box`) |
| Code by concept/domain ("authentication", "payment") | Cartographing Kittens (`search`) — after annotation |
| A specific string/pattern/TODO | grep/glob |

## Decision heuristic

When you get a request, follow this mental model and delegate to the appropriate sub-skill:

1. **Structural/relational question?** (definitions, imports, call chains, file contents, class hierarchy)
   → Use **`kitty:explore`** — uses `get_context_summary`, `batch_query_nodes`, `rank_nodes` for efficient multi-file/multi-symbol exploration.

2. **Planning a change?** (blast radius, what breaks, dependency analysis)
   → Use **`kitty:impact`** — uses `find_dependents`, `find_dependencies`, `rank_nodes`, `validate_graph` for comprehensive impact context.

3. **Verifying structural health?** (cycles, orphans, missing edges)
   → Use `validate_graph(scope=...)` directly, or **`kitty:impact`** for full analysis.

4. **What's most important here?** (key symbols, high-connectivity nodes)
   → Use `rank_nodes(scope=..., kind=..., limit=N)` directly, or through **`kitty:explore`**.

5. **What changed structurally?** (after code modifications)
   → Use `graph_diff(file_paths=[...])` after `index_codebase()` to see structural diffs.

6. **Planning, working, or reviewing?**
   → Query memory first: `query_litter_box` for lessons to avoid and `query_treat_box`
   for validated patterns to follow. Record new durable lessons with
   `add_litter_box_entry` or `add_treat_box_entry` after validated failures or successes.

7. **Semantic/domain question?** ("find all auth code", "what handles payments?")
   → Check `annotation_status`. If many nodes are pending, use **`kitty:annotate`**
   first, then `search`. Use `find_stale_annotations` to detect outdated annotations.

8. **Plain text search?** (string literal, error message, TODO)
   → Fall back to grep/glob. Cartographing Kittens isn't a text search engine.

## Tool skills

| Sub-skill | Purpose |
|---|---|
| `kitty:explore` | Structural exploration — browse definitions, imports, relationships, importance |
| `kitty:impact` | Impact analysis — blast radius, dependency chains, importance, structural health |
| `kitty:annotate` | Enrich graph with summaries and tags for semantic search |

## Direct tools (for ad-hoc use outside sub-skills)

| Tool | Purpose |
|---|---|
| `graph_diff` | Structural diff after indexing — see what changed |
| `validate_graph` | Structural health checks — cycles, orphans, missing edges |
| `batch_query_nodes` | Multi-node query — look up several symbols at once |
| `get_context_summary` | Token-efficient context — overview of files and symbols |
| `find_stale_annotations` | Detect annotations invalidated by code changes |
| `rank_nodes` | Importance scoring — find the most connected/critical symbols |
| `query_litter_box` | Retrieve failures, regressions, unsupported paths, and anti-patterns to avoid |
| `query_treat_box` | Retrieve best practices, validated patterns, conventions, and optimizations to follow |
| `add_litter_box_entry` | Persist a reusable negative lesson discovered during work or review |
| `add_treat_box_entry` | Persist a reusable positive lesson validated during planning, work, or review |

## Workflow skills

Full engineering pipeline powered by Cartographing Kittens agent swarms:

| Skill | Purpose |
|---|---|
| `kitty:brainstorm` | Requirements gathering with Cartographing Kittens-powered research swarms |
| `kitty:plan` | Technical planning with parallel research agents for deep codebase understanding |
| `kitty:work` | Execute plans with Cartographing Kittens-first worker swarms |
| `kitty:review` | Multi-agent code review with structural impact analysis |
| `kitty:lfg` | Full autonomous pipeline: plan → work → review (no interaction needed) |

Pipeline: `kitty:brainstorm` → `kitty:plan` → `kitty:work` → `kitty:review`

Or use `kitty:lfg` to run plan → work → review autonomously.

## Quick start

1. **First use or stale index** → call `index_codebase(full=false)` for incremental, `full=true` for full reindex
2. **Explore structure** → use `kitty:explore`
3. **Assess change impact** → use `kitty:impact`
4. **Enable semantic search** → use `kitty:annotate`
5. **Build a feature** → use `kitty:lfg "feature description"` for full autonomous pipeline

## Key conventions

- **Qualified names** use `::` separator: `module.path::ClassName::method_name`
- **Edge kinds** for filtering: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- **Node kinds**: `module`, `class`, `function`, `method`, `variable`
- By default the graph lives in `.pawprints/graph.db` inside the project root
- Set `KITTY_STORAGE_ROOT` to keep per-project graph data under a centralized storage root instead
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
- Query litter/treat memory before planning, work, and review; record durable lessons after validation
- Combine sub-skills: explore first, then assess impact before changing code
- For large codebases (50+ pending nodes), `kitty:annotate` supports parallel subagents
- See `references/tool-reference.md` for full tool parameter details
- See `references/memory-workflow.md` for the required memory preflight/postflight protocol
