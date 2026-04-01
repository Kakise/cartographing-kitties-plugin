# Cat-Themed Rebranding + Memory System + Commands -- Requirements

## Problem Frame

The project needs a cohesive cat/kitten-themed brand identity that matches the vision described by the maintainer. Currently "Cartograph" is the dominant brand name across user-facing surfaces (skills, agents, web UI, docs, prompts), while some elements are already cat-themed (package name `cartographing-kittens`, CLI `kitty-graph`). The rebrand also introduces two new concepts -- memory systems (litter-box / treat-box) and slash commands -- that don't exist yet.

## Codebase Context

### Current State (from Cartograph research)

- **467 occurrences** of "cartograph" across 73 files
- **Python module** stays `src/cartograph/` (internal, not rebranded)
- **Already cat-themed**: PyPI package `cartographing-kittens`, CLI commands `cartographing-kittens` and `kitty-graph`, GitHub repo `cartographing-kittens`, email `cartographing-kittens@a-smol-cat.fr`
- **MCP tool names** are generic (no "cartograph" in them): `index_codebase`, `query_node`, etc. -- no change needed
- **MCP prompt names** are generic: `explore_codebase`, `plan_refactor`, `annotate_batch` -- no change needed
- **Agents with roles do NOT have access to MCP tools** -- skills dispatch agents, but agents use Bash/Read/Grep/Glob only. Any rebranding of agent markdown must not assume MCP access.

### Cat Role Mapping

| Cat Role | Current Equivalent | Purpose |
|----------|-------------------|---------|
| **Master Cat (Plaid)** | Skill router + `plan`/`work`/`lfg` skills | Orchestrates actions, spawns kittens, creates commits |
| **Cartographing-kittens** | `index_codebase` tool + `annotate` skill/agents | Index codebase into AST/SQLite, annotate graph nodes |
| **Expert Kittens** | `work` skill workers + `correctness`/`structure` reviewers | Make modifications, check for regressions |
| **Librarian-kittens** | `impact`/`flow`/`pattern`/`researcher` agents | Gap analysis, impact assessment, research |

## Requirements

### R1. Rebrand User-Facing Skill Names

Rename all 9 skill IDs and their directory names:

| Current | New |
|---------|-----|
| `cartograph` | `kitty` (router) |
| `cartograph:explore` | `kitty:explore` |
| `cartograph:impact` | `kitty:impact` |
| `cartograph:annotate` | `kitty:annotate` |
| `cartograph:brainstorm` | `kitty:brainstorm` |
| `cartograph:plan` | `kitty:plan` |
| `cartograph:work` | `kitty:work` |
| `cartograph:review` | `kitty:review` |
| `kitty:lfg` | `kitty:lfg` |

Update all `name:` fields in SKILL.md frontmatter, directory names, and cross-references between skills.

### R2. Rebrand Agent Names with Cat Role Prefixes

Rename all 9 agents to reflect their cat role:

| Current | New | Cat Role |
|---------|-----|----------|
| `cartograph-annotator` | `cartographing-kitten` | Cartographing-kitten |
| `cartograph-researcher` | `librarian-kitten-researcher` | Librarian-kitten |
| `cartograph-pattern-analyst` | `librarian-kitten-pattern` | Librarian-kitten |
| `cartograph-impact-analyst` | `librarian-kitten-impact` | Librarian-kitten |
| `cartograph-flow-analyzer` | `librarian-kitten-flow` | Librarian-kitten |
| `cartograph-correctness-reviewer` | `expert-kitten-correctness` | Expert Kitten |
| `cartograph-testing-reviewer` | `expert-kitten-testing` | Expert Kitten |
| `cartograph-impact-reviewer` | `expert-kitten-impact` | Expert Kitten |
| `cartograph-structure-reviewer` | `expert-kitten-structure` | Expert Kitten |

Update filenames, `name:` fields in frontmatter, and all references in SKILL.md files that dispatch these agents.

### R3. Rebrand Plugin Manifests

- `plugins/cartograph/.claude-plugin/plugin.json`: rename `"name": "cartograph"` to `"name": "kitty"`
- `.claude-plugin/marketplace.json`: update plugin name and source path
- Rename plugin directory from `plugins/cartograph/` to `plugins/kitty/`

### R4. Rebrand MCP Server Name

Change `FastMCP("cartograph", ...)` to `FastMCP("kitty", ...)` in `src/cartograph/server/main.py`.

### R5. Rebrand Web Explorer

- HTML title: `Cartograph Graph Explorer` -> `Kitty Graph Explorer` (or `Cartographing Kittens`)
- `<h1>Cartograph</h1>` -> `<h1>Cartographing Kittens</h1>`
- Server startup message: update to match

### R6. Rebrand Documentation

- `CLAUDE.md`: replace all user-facing "Cartograph" references with cat-themed names, update skill/agent tables
- `README.md`: full rebrand of user-facing text
- All SKILL.md files: update prose references to "Cartograph" with cat-themed language
- All agent .md files: update prose references
- Prompt output text in `src/cartograph/server/prompts/`: update "Cartograph's structural tools" etc.

### R7. Rebrand Environment Variable and Data Directory

- `CARTOGRAPH_PROJECT_ROOT` -> `KITTY_PROJECT_ROOT` (support both during transition period)
- `.cartograph/` directory name -> `.pawprints/` (auto-migrate existing `.cartograph/` directories)

### R8. Implement Litter-Box Memory (Negative Knowledge)

A persistent memory system for failures, anti-patterns, unsupported operations, and things to never do.

- **Storage**: New SQLite table in graph.db + markdown export at `.pawprints/litter-box.md`
- **Schema**: `(id, category, description, context, created_at, source_agent)`
- **Categories**: `failure`, `anti-pattern`, `unsupported`, `regression`, `never-do`
- **New MCP tools**: `add_litter_box_entry`, `query_litter_box`
- **Agent integration**: Expert Kittens (reviewers) should check litter-box before reviewing; worker agents should check before implementing
- **Skill integration**: `kitty:work` and `kitty:review` skills should instruct agents to consult litter-box

### R9. Implement Treat-Box Memory (Positive Knowledge)

A persistent memory system for best practices, validated patterns, and things to always do.

- **Storage**: New SQLite table in graph.db + markdown export at `.pawprints/treat-box.md`
- **Schema**: `(id, category, description, context, created_at, source_agent)`
- **Categories**: `best-practice`, `validated-pattern`, `always-do`, `convention`, `optimization`
- **New MCP tools**: `add_treat_box_entry`, `query_treat_box`
- **Agent integration**: Same as litter-box -- agents consult treat-box for positive guidance
- **Skill integration**: `kitty:plan` and `kitty:work` skills should instruct agents to consult treat-box

### R10. Add Slash Commands (Minimal Set)

Add a `commands/` directory to the plugin with 3 essential commands:

| Command | Purpose | Maps to |
|---------|---------|---------|
| `/kitty-index` | Quick index/re-index the codebase | Calls `index_codebase` tool |
| `/kitty-explore` | Explore codebase structure | Invokes `kitty:explore` skill |
| `/kitty-status` | Show index status + annotation coverage + memory stats | Calls `annotation_status` + litter/treat box counts |

Each command is a `.md` file with YAML frontmatter (`description`, `allowed-tools`) in `plugins/kitty/commands/`.

## Success Criteria

- All user-facing surfaces say "kitty" / "kitten" instead of "cartograph"
- Python internals (`src/cartograph/`, imports) remain unchanged
- Skills invoke correctly with `kitty:*` prefix
- Agents dispatch correctly with new names
- Litter-box and treat-box persist entries across sessions in SQLite + markdown
- 3 slash commands work and appear in `/help`
- All existing tests pass (with updated references where needed)
- Web explorer shows cat-themed branding

## Scope Boundaries

### In scope
- All user-facing naming (skills, agents, plugin manifests, web UI, docs, prompts)
- Memory system (litter-box + treat-box) with DB + markdown export
- 3 slash commands
- Environment variable and data directory rename (with backward compat)
- CLAUDE.md and README.md updates

### Out of scope
- Renaming the Python module directory (`src/cartograph/` stays)
- Renaming Python import paths
- Changing MCP tool function names (already generic)
- Changing MCP prompt function names (already generic)
- Logo/visual design assets
- Cat ASCII art or emoji in code

## Key Decisions

- **Internal module name preserved**: `src/cartograph/` stays to avoid 100+ import changes across 40 files. Only user-facing names change.
- **"kitty" as the brand prefix**: Short, consistent, maps well to skill IDs (`kitty:plan`) and commands (`/kitty-status`).
- **Cat roles in agent names**: Agents are prefixed with their role (`librarian-kitten-*`, `expert-kitten-*`, `cartographing-kitten`) for clarity.
- **Auto-migrate data dir**: Rename `.cartograph/` to `.pawprints/` on first run; support `CARTOGRAPH_PROJECT_ROOT` as fallback env var during transition.
- **Memory in both DB and markdown**: SQLite for structured queries by agents; markdown for human readability and version control.

## Open Questions

### Resolve Before Planning
- (Resolved) Env var: support both `KITTY_PROJECT_ROOT` and `CARTOGRAPH_PROJECT_ROOT` during transition
- (Resolved) Data dir: auto-migrate `.cartograph/` -> `.pawprints/` on first run
- (Resolved) Data dir name: `.pawprints/` (cats leave pawprints -- traces through your code)

### Deferred
- Should litter-box/treat-box entries have an expiry or relevance score that decays over time?
- Should there be a `/kitty-remember` command that lets users manually add entries to either box?
- Should the web explorer have cat-themed visual elements (paw icons, cat silhouettes)?
