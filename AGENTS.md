# Cartographing Kittens

AST-powered codebase intelligence framework for AI coding agents — Codex runtime entrypoint.

This file mirrors `CLAUDE.md` for the Codex CLI. The two files share a section
structure that is enforced by `scripts/sync_claude_agents_md.py` (run on every
commit via pre-commit). Codex-specific differences live inside the sections
listed in the script's allow-list — primarily packaging paths and the local-dev
invocation. Edits that introduce a new H2 section in one file but not the other
must update the allow-list.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Parsing | `src/cartograph/parsing/` | Tree-sitter AST extraction for Python, TypeScript, JavaScript |
| Indexing | `src/cartograph/indexing/` | File discovery, incremental change detection, cross-file resolution |
| Storage | `src/cartograph/storage/` | SQLite graph database with FTS5 search and recursive CTE traversal |
| Annotation | `src/cartograph/annotation/` | LLM-driven semantic enrichment (summaries, tags, roles) |
| Memory | `src/cartograph/memory/` | Litter-box (negative) and treat-box (positive) persistent memory |
| MCP Server | `src/cartograph/server/` | FastMCP server — structural query, annotation, memory, and workflow tools |
| Server Tools | `src/cartograph/server/tools/` | Tool implementations (index, query, analysis, annotate, memory, reactive) |
| Server Prompts | `src/cartograph/server/prompts/` | Prompt implementations (explore, refactor, annotate) |
| Web | `src/cartograph/web/` | Web-based graph viewer / browser UI |

## Conventions

- Qualified names use `::` separator: `module.path::ClassName::method_name`
- Edge kinds: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- Node kinds: `module`, `class`, `function`, `method`, `variable`
- Graph stored at `.pawprints/graph.db` in project root by default
- Set `KITTY_STORAGE_ROOT` to place per-project graph data under a centralized storage directory
- Indexing is incremental by default — only changed files are re-parsed
- `query_node`, `search`, `rank_nodes`, `get_context_summary`, and `get_file_structure`
  responses include a `centrality` field — a weighted-PageRank score in `[0, 1]` reflecting
  each node's structural importance. The cache is refreshed lazily on first read after the
  graph changes.
- Plans under `docs/plans/` carry machine-readable state (frontmatter `status` + per-unit
  `**State:**` lines). See `docs/architecture/plan-state-conventions.md`. The
  `/kitty-plans` slash command (or `uv run python scripts/plan_status.py report`) renders the
  cross-plan dashboard; `audit` runs in pre-commit.
- Codex executes the framework subagents declared in
  `plugins/kitty/agents/manifest.json` inline. Where Claude Code uses
  `AskUserQuestion` for handoff menus, Codex skills present the same options as
  numbered text prompts and pipeline modes (`kitty:lfg`, `mode:autofix`,
  `mode:report-only`, autonomous loops) skip the prompt by selecting the
  recommended option.

## Plugin Structure (Marketplace Layout)

```
plugins/
  kitty/                         # Plugin root (marketplace layout)
    .codex/
      config.toml                # Codex runtime defaults (max_threads, depth, runtime cap)
      agents/*.toml              # Codex-flavored agent manifests (regenerated from _source)
    .claude-plugin/plugin.json   # Plugin manifest (uvx-based MCP server)
    skills/                      # Git submodule → Kakise/cartographing-kitties-skills
      kitty/                     # Router skill — delegates to sub-skills
        SKILL.md
        references/
          tool-reference/        # Generated detailed tool parameter docs by family
          annotation-workflow.md # Annotation workflow guide
      kitty-explore/             # Structural exploration
      kitty-impact/              # Impact analysis and refactoring
      kitty-annotate/            # Annotation workflow
      kitty-brainstorm/          # Requirements gathering with research swarms
      kitty-plan/                # Technical planning with 4 research agents
      kitty-work/                # Execution with Cartographing Kittens-first workers
        agents/openai.yaml       # Codex implicit-invocation policy (orchestrator skills)
      kitty-review/              # Multi-agent review with structural analysis
      kitty-lfg/                 # Full autonomous pipeline (plan → work → review)
        agents/openai.yaml       # Codex implicit-invocation policy (orchestrator skills)
    agents/
      manifest.json             # Runtime-neutral declaration of framework subagents
      cartographing-kitten.md    # Batch annotation specialist
      librarian-kitten-researcher.md   # General codebase researcher
      librarian-kitten-pattern.md # Pattern and convention finder
      librarian-kitten-impact.md  # Blast radius analyzer
      librarian-kitten-flow.md   # Call chain and data flow tracer
      expert-kitten-correctness.md # Logic errors, edge cases (always-on)
      expert-kitten-testing.md     # Test coverage gaps (always-on)
      expert-kitten-impact.md      # Blast radius review (conditional)
      expert-kitten-structure.md   # Architecture review (conditional)
    _source/
      agents/*.yaml             # Single source of truth for generated agents
      manifests/plugin.yaml     # Single source of truth for plugin manifests
      templates/*.j2            # Generator templates for runtime artifacts
src/cartograph/                  # Python source (MCP server + core library)
tests/                           # Test suite
.claude-plugin/                  # Claude Code plugin marketplace manifest
.codex-plugin/                   # Codex runtime plugin manifest (dual-runtime support)
scripts/                         # Repo-level developer scripts
```

Generated harness artifacts must be edited through `plugins/kitty/_source/`, not by
hand. Run `uv run python scripts/generate_agents.py` after changing
`_source/agents/*.yaml`, and run `uv run python scripts/generate_manifests.py`
after changing `_source/manifests/plugin.yaml`. CI and pre-commit use the
matching `--check` commands plus `scripts/validate_skills.py` and
`scripts/sync_claude_agents_md.py --check` to catch drift.

`plugins/kitty/skills/` is a Git submodule that points at
[`Kakise/cartographing-kitties-skills`](https://github.com/Kakise/cartographing-kitties-skills).
Bootstrap it on first clone with `git submodule update --init --recursive`.
Skill edits land via PRs against that submodule repo. Framework agents under
`plugins/kitty/agents/` stay in this repo because they are generated from
`plugins/kitty/_source/agents/*.yaml`.

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

## MCP Tool Surface

### Annotation

| Tool | Purpose |
|------|---------|
| `get_pending_annotations` | Fetch pending nodes with source, neighbor context, seed taxonomy, `recommended_model_tier`, and `requeue_reason` when present. |
| `submit_annotations` | Persist generated summaries, tags, and roles, or mark ambiguous nodes failed. |
| `find_low_quality_annotations` | Audit annotated nodes for placeholder summaries, too-short summaries, missing name references, and generic fallback roles. |
| `requeue_low_quality_annotations` | Move low-quality annotations back to pending; dry-run by default and caps repeat requeues by marking failed. |

### Workflow Contract

The framework subagents remain part of the repository for both Claude Code and Codex.

- Codex preserves the same subagents through `plugins/kitty/agents/manifest.json` and the
  Codex-flavored manifests under `plugins/kitty/.codex/agents/*.toml`. Execution is
  inline-first because the local Codex manifest spec does not define an explicit `agents`
  field.
- Skills must therefore make sense without assuming swarm orchestration.
- Orchestrator skills (`kitty:work`, `kitty:lfg`) ship `agents/openai.yaml` with
  `allow_implicit_invocation: false` so Codex never auto-invokes them.

Canonical reference: `docs/architecture/codex-workflow-contract.md`.
Repository boundary reference: `docs/architecture/repo-boundaries.md`.

When runtime support is available, the framework may delegate as follows:

**kitty:brainstorm** may use:
- `librarian-kitten-researcher` (architecture, stack)
- `librarian-kitten-pattern` (existing patterns)

**kitty:plan** may use:
- `librarian-kitten-researcher` (architecture)
- `librarian-kitten-pattern` (patterns)
- `librarian-kitten-flow` (call chains)
- `librarian-kitten-impact` (blast radius)

**kitty:work** may use worker delegation per implementation unit:
- Each worker calls `get_file_structure` + `query_node` before implementing
- Independent units can run in parallel when the runtime supports it cleanly

**kitty:review** may use:
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
uv run pre-commit install     # Install git hooks (one-time)
uv run pre-commit run --all-files  # Run hooks against all files
```

## MCP Server (local dev)

Codex resolves the MCP server through `.codex-plugin/plugin.json` →
`plugins/kitty/.mcp.json`. To run the server directly while iterating on
tool changes:

```bash
uv run python -m cartograph.server.main   # Start server via stdio
```

Codex agent runtime defaults live in `plugins/kitty/.codex/config.toml`
(`max_threads`, `max_depth`, `job_max_runtime_seconds`) — adjust there rather
than per-skill so Claude Code parity is preserved.

## Testing

Tests live in `tests/`. Fixtures in `tests/fixtures/` are sample projects — not test modules.
Run with `uv run pytest`. CI matrix tests Python 3.13-3.14.
