# Cartograph

AST-powered codebase intelligence framework for AI coding agents.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Parsing | `src/cartograph/parsing/` | Tree-sitter AST extraction for Python, TypeScript, JavaScript |
| Indexing | `src/cartograph/indexing/` | File discovery, incremental change detection, cross-file resolution |
| Storage | `src/cartograph/storage/` | SQLite graph database with FTS5 search and recursive CTE traversal |
| Annotation | `src/cartograph/annotation/` | LLM-driven semantic enrichment (summaries, tags, roles) |
| MCP Server | `src/cartograph/server/` | FastMCP server — 9 tools, 3 prompts |
| Server Tools | `src/cartograph/server/tools/` | Tool implementations (index, query, analysis, annotate) |
| Server Prompts | `src/cartograph/server/prompts/` | Prompt implementations (explore, refactor, annotate) |

## Conventions

- Qualified names use `::` separator: `module.path::ClassName::method_name`
- Edge kinds: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- Node kinds: `module`, `class`, `function`, `method`, `variable`
- Graph stored at `.cartograph/graph.db` in project root
- Indexing is incremental by default — only changed files are re-parsed

## Plugin Structure (Marketplace Layout)

```
plugins/
  cartograph/                    # Plugin root (marketplace layout)
    .claude-plugin/plugin.json   # Plugin manifest (uvx-based MCP server)
    skills/
      cartograph/                # Router skill — delegates to sub-skills
        SKILL.md
        references/
          tool-reference.md      # Detailed tool parameter docs
          annotation-workflow.md # Annotation workflow guide
      cartograph-explore/        # Structural exploration
      cartograph-impact/         # Impact analysis and refactoring
      cartograph-annotate/       # Annotation workflow
      cartograph-brainstorm/     # Requirements gathering with research swarms
      cartograph-plan/           # Technical planning with 4 research agents
      cartograph-work/           # Execution with Cartograph-first workers
      cartograph-review/         # Multi-agent review with structural analysis
      cartograph-lfg/            # Full autonomous pipeline (plan → work → review)
    agents/
      cartograph-annotator.md    # Batch annotation specialist
      cartograph-researcher.md   # General codebase researcher
      cartograph-pattern-analyst.md # Pattern and convention finder
      cartograph-impact-analyst.md  # Blast radius analyzer
      cartograph-flow-analyzer.md   # Call chain and data flow tracer
      cartograph-correctness-reviewer.md # Logic errors, edge cases (always-on)
      cartograph-testing-reviewer.md     # Test coverage gaps (always-on)
      cartograph-impact-reviewer.md      # Blast radius review (conditional)
      cartograph-structure-reviewer.md   # Architecture review (conditional)
src/cartograph/                  # Python source (MCP server + core library)
tests/                           # Test suite
```

## Workflow Pipeline

```
cartograph:brainstorm → cartograph:plan → cartograph:work → cartograph:review
```

Or use `cartograph:lfg` for full autonomous execution (plan → work → review).

### When to use each skill

| Situation | Skill |
|-----------|-------|
| Exploring code structure | `cartograph:explore` |
| Understanding change impact | `cartograph:impact` |
| Enabling semantic search | `cartograph:annotate` |
| Gathering requirements for a feature | `cartograph:brainstorm` |
| Planning implementation | `cartograph:plan` |
| Building features | `cartograph:work` |
| Reviewing code changes | `cartograph:review` |
| Full autonomous pipeline | `cartograph:lfg` |

### How skills dispatch agents

**cartograph:brainstorm** dispatches in parallel:
- `cartograph-researcher` (architecture, stack)
- `cartograph-pattern-analyst` (existing patterns)

**cartograph:plan** dispatches in parallel:
- `cartograph-researcher` (architecture)
- `cartograph-pattern-analyst` (patterns)
- `cartograph-flow-analyzer` (call chains)
- `cartograph-impact-analyst` (blast radius)

**cartograph:work** dispatches workers per implementation unit:
- Each worker calls `get_file_structure` + `query_node` before implementing
- Independent units run as parallel swarm

**cartograph:review** dispatches in parallel:
- `cartograph-correctness-reviewer` (always)
- `cartograph-testing-reviewer` (always)
- `cartograph-impact-reviewer` (when 3+ files changed)
- `cartograph-structure-reviewer` (when new files created)

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

## Cartograph-First Principle

All agents and skills use Cartograph MCP tools as primary codebase intelligence:

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
