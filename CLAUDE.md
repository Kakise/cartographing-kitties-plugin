# Cartographing Kittens

AST-powered codebase intelligence framework for AI coding agents.

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Parsing | `src/cartograph/parsing/` | Tree-sitter AST extraction for Python, TypeScript, JavaScript, Rust, C++ |
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
- Skills ask the user via Claude Code's `AskUserQuestion` tool whenever 2-4
  enumerable options exist (handoff menus, triage decisions, clarifying
  questions). Pipeline modes (`kitty:lfg`, `mode:autofix`, `mode:report-only`,
  autonomous loops) skip prompts and pick the recommended option silently. See
  `plugins/kitty/skills/kitty/references/ask-user-protocol.md` for the full
  contract and worked examples.

## Skill and Subagent Authoring

Skills and subagents are generated from `plugins/kitty/_source/`. Edit the
YAML sources, then run the generators (see Plugin Structure section). The
following rules — drawn from Anthropic's current spec — are enforced by
`scripts/validate_skills.py` and by the generators:

- **Skill `name:`** must match `^[a-z0-9-]{1,64}$` (lowercase, numbers,
  hyphens; no colons). The plugin namespace prefix (`kitty:`) is added
  automatically by Claude Code from the plugin name, so the user-facing
  command for a directory `kitty-plan/` becomes `/kitty:kitty-plan`. Do not
  encode the colon inside the YAML.
- **Skill `description:`** is ≤1024 chars and leads with the trigger phrase a
  user would actually type. The combined `description` + `when_to_use` is
  capped at 1,536 chars when Claude lists the skill.
- **Skill `when_to_use:`** holds extra trigger keywords without crowding the
  always-visible description. Use it on high-traffic skills.
- **Skill body** stays under 500 lines; move details to `references/`.
- **MCP tools** appear in `allowed-tools:` (for skills) and `tools:` (for
  subagents) with their fully-qualified Claude Code names, e.g.
  `mcp__plugin_kitty_kitty__query_node`. Built-in tools keep their short
  names (`Read`, `Grep`, `Glob`, `Bash`, `Write`, `Edit`).
- **Subagent `tools:`** is an allowlist — setting it denies every unlisted
  tool, including all MCP tools. Omit `tools:` to inherit the full toolset
  from the main conversation; list `mcp__plugin_kitty_kitty__<tool>`
  explicitly only when narrowing on purpose.
- **Subagent descriptions** use third-person, present tense, and lead with
  the trigger phrase. Always-on agents include "Use proactively …"; on-
  demand agents include "Spawn when …".
- **Subagent `color:`** must be one of `red, blue, green, yellow, purple,
  orange, pink, cyan`. The generator (`scripts/generate_agents.py`)
  raises on any other value.

Authoritative sources:
[Skills](https://code.claude.com/docs/en/skills) ·
[Subagents](https://code.claude.com/docs/en/sub-agents) ·
[Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

## Plugin Structure (Marketplace Layout)

```
plugins/
  kitty/                         # Plugin root (marketplace layout)
    .claude-plugin/plugin.json   # Plugin manifest (uvx-based MCP server)
    skills/                      # Generated skills (from _source/skills)
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
      kitty-review/              # Multi-agent review with structural analysis
      kitty-lfg/                 # Full autonomous pipeline (plan → work → review)
      kitty-install-codex/       # Manual Codex asset installer helper
    prompts/                     # Codex prompt commands generated from _source/commands
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
      commands/*.yaml           # Single source of truth for command/prompt outputs
      manifests/plugin.yaml     # Single source of truth for plugin manifests
      skills/*.yaml             # Single source of truth for generated skills
      templates/*.j2            # Generator templates for runtime artifacts
src/cartograph/                  # Python source (MCP server + core library)
tests/                           # Test suite
.claude-plugin/                  # Claude Code plugin marketplace manifest
.codex-plugin/                   # Codex runtime plugin manifest (dual-runtime support)
scripts/                         # Repo-level developer scripts
```

Generated harness artifacts must be edited through `plugins/kitty/_source/`, not by
hand. Run `uv run python scripts/generate_agents.py` after changing
`_source/agents/*.yaml`, `uv run python scripts/generate_skills.py` after changing
`_source/skills/*.yaml`, `uv run python scripts/generate_commands.py` after changing
`_source/commands/*.yaml`, and `uv run python scripts/generate_manifests.py` after changing
`_source/manifests/plugin.yaml`. CI and pre-commit use the
matching `--check` commands plus `scripts/validate_skills.py` to catch drift.

`plugins/kitty/skills/` is vendored in this repository and generated from
`plugins/kitty/_source/skills/*.yaml`. Framework agents under `plugins/kitty/agents/`
and `plugins/kitty/.codex/agents/` are generated from `plugins/kitty/_source/agents/*.yaml`.

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

- Claude Code is expected to discover `agents/` from the preserved plugin directory layout.
- Codex preserves the same subagents through generated custom-agent TOML files under
  `plugins/kitty/.codex/agents/*.toml`.
- Skills must still make sense without assuming swarm orchestration.

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

```bash
uv run python -m cartograph.server.main   # Start server via stdio
```

## Testing

Tests live in `tests/`. Fixtures in `tests/fixtures/` are sample projects — not test modules.
Run with `uv run pytest`. CI matrix tests Python 3.13-3.14.
