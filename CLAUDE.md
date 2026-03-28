# Cartographing Kittens

AST-powered codebase intelligence framework for AI coding agents.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Parsing | `src/cartograph/parsing/` | Tree-sitter AST extraction for Python, TypeScript, JavaScript |
| Indexing | `src/cartograph/indexing/` | File discovery, incremental change detection, cross-file resolution |
| Storage | `src/cartograph/storage/` | SQLite graph database with FTS5 search and recursive CTE traversal |
| Annotation | `src/cartograph/annotation/` | LLM-driven semantic enrichment (summaries, tags, roles) |
| Memory | `src/cartograph/memory/` | Litter-box (negative) and treat-box (positive) persistent memory |
| MCP Server | `src/cartograph/server/` | FastMCP server — 13 tools, 3 prompts |
| Server Tools | `src/cartograph/server/tools/` | Tool implementations (index, query, analysis, annotate, memory) |
| Server Prompts | `src/cartograph/server/prompts/` | Prompt implementations (explore, refactor, annotate) |

## Conventions

- Qualified names use `::` separator: `module.path::ClassName::method_name`
- Edge kinds: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- Node kinds: `module`, `class`, `function`, `method`, `variable`
- Graph stored at `.pawprints/graph.db` in project root
- Indexing is incremental by default — only changed files are re-parsed

## Plugin Structure (Marketplace Layout)

```
plugins/
  kitty/                         # Plugin root (marketplace layout)
    .claude-plugin/plugin.json   # Plugin manifest (uvx-based MCP server)
    skills/
      kitty/                     # Router skill — delegates to sub-skills
        SKILL.md
        references/
          tool-reference.md      # Detailed tool parameter docs
          annotation-workflow.md # Annotation workflow guide
      kitty-explore/             # Structural exploration
      kitty-impact/              # Impact analysis and refactoring
      kitty-annotate/            # Annotation workflow
      kitty-brainstorm/          # Requirements gathering with research swarms
      kitty-plan/                # Technical planning with 4 research agents
      kitty-work/                # Execution with Cartographing Kittens-first workers
      kitty-review/              # Multi-agent review with structural analysis
      kitty-lfg/                 # Full autonomous pipeline (plan → work → review)
    agents/
      cartographing-kitten.md    # Batch annotation specialist
      librarian-kitten-researcher.md   # General codebase researcher
      librarian-kitten-pattern.md # Pattern and convention finder
      librarian-kitten-impact.md  # Blast radius analyzer
      librarian-kitten-flow.md   # Call chain and data flow tracer
      expert-kitten-correctness.md # Logic errors, edge cases (always-on)
      expert-kitten-testing.md     # Test coverage gaps (always-on)
      expert-kitten-impact.md      # Blast radius review (conditional)
      expert-kitten-structure.md   # Architecture review (conditional)
src/cartograph/                  # Python source (MCP server + core library)
tests/                           # Test suite
```

## Workflow Pipeline

```
kitty:brainstorm → kitty:plan → kitty:work → kitty:review
```

Or use `kitty:lfg` for full autonomous execution (plan → work → review).

### When to use each skill

| Situation | Skill |
|-----------|-------|
| Exploring code structure | `kitty:explore` |
| Understanding change impact | `kitty:impact` |
| Enabling semantic search | `kitty:annotate` |
| Gathering requirements for a feature | `kitty:brainstorm` |
| Planning implementation | `kitty:plan` |
| Building features | `kitty:work` |
| Reviewing code changes | `kitty:review` |
| Full autonomous pipeline | `kitty:lfg` |

### How skills dispatch agents

**kitty:brainstorm** dispatches in parallel:
- `librarian-kitten-researcher` (architecture, stack)
- `librarian-kitten-pattern` (existing patterns)

**kitty:plan** dispatches in parallel:
- `librarian-kitten-researcher` (architecture)
- `librarian-kitten-pattern` (patterns)
- `librarian-kitten-flow` (call chains)
- `librarian-kitten-impact` (blast radius)

**kitty:work** dispatches workers per implementation unit:
- Each worker calls `get_file_structure` + `query_node` before implementing
- Independent units run as parallel swarm

**kitty:review** dispatches in parallel:
- `expert-kitten-correctness` (always)
- `expert-kitten-testing` (always)
- `expert-kitten-impact` (when 3+ files changed)
- `expert-kitten-structure` (when new files created)

## Agent Output Contracts

Research agents return structured text summaries with:
- Technology & stack, architecture, patterns, key files, dependencies, conventions

Review agents return JSON:
```json
{
  "reviewer": "agent-name",
  "findings": [{
    "severity": "P0|P1|P2|P3",
    "category": "...",
    "location": "file:line",
    "issue": "description",
    "guidance": "how to fix",
    "confidence": 0.85,
    "autofix_class": "safe_auto|gated_auto|manual|advisory"
  }],
  "summary": "overall assessment"
}
```

## Cartographing Kittens-First Principle

All agents and skills use Cartographing Kittens MCP tools as primary codebase intelligence:

| Need | Tool | NOT |
|------|------|----|
| Understand a file's structure | `get_file_structure` | Reading entire file |
| Find what depends on X | `find_dependents` | Grep for import statements |
| Understand a symbol | `query_node` | Grep for the name |
| Find code by domain | `search` (after annotation) | Grep for keywords |
| Assess change impact | `find_dependents` + `find_dependencies` | Manual file reading |

Fall back to grep/glob only for text-literal searches (error messages, string constants, TODOs).

## Development

```bash
uv sync --all-extras          # Install dependencies
uv run pytest                 # Run tests
uv run ruff check src/        # Lint
uv run ruff format --check src/  # Format check
uv run basedpyright --level error  # Type check
uv run codespell src          # Spell check
```

## MCP Server (local dev)

```bash
uv run python -m cartograph.server.main   # Start server via stdio
```

## Testing

Tests live in `tests/`. Fixtures in `tests/fixtures/` are sample projects — not test modules.
Run with `uv run pytest`. CI matrix tests Python 3.11-3.14.
