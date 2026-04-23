# Cartographing Kittens

AST-powered codebase intelligence for AI coding agents.

Cartographing Kittens parses your code with [tree-sitter](https://tree-sitter.github.io/tree-sitter/), builds a structural graph in SQLite, and exposes it as an [MCP](https://modelcontextprotocol.io/) server. It answers questions that grep can't: *what depends on this function?*, *what breaks if I change this class?*, *show me all the auth-related code*.

It is also available with repo-local integrations for **OpenCode**, **Codex**, **Claude Code**, and **Gemini**, plus a complete engineering workflow framework for brainstorm, plan, implement, and review loops powered by Cartographing Kittens.

## Install in OpenCode

This repository now includes a project-local OpenCode setup:

- [`opencode.json`](./opencode.json) wires in the Cartographing Kittens MCP server
- [`.opencode/skills`](./.opencode/skills) exposes the `kitty` workflow as OpenCode skills
- [`.opencode/commands`](./.opencode/commands) adds slash commands like `/kitty-plan` and `/kitty-review`
- [`.opencode/agents`](./.opencode/agents) ports the research, annotation, and review subagents

### Use from a checkout

Clone the repository and open it in OpenCode:

```bash
git clone https://github.com/Kakise/cartographing-kitties-plugin.git ~/src/cartographing-kitties-plugin
cd ~/src/cartographing-kitties-plugin
opencode
```

OpenCode will discover `opencode.json` and `.opencode/` automatically.

### Install globally in OpenCode

If you want Cartographing Kittens available in every project, install its OpenCode assets into your global OpenCode config directory.

1. Clone this repository somewhere stable:

```bash
git clone https://github.com/Kakise/cartographing-kitties-plugin.git ~/src/cartographing-kitties-plugin
```

2. Run the helper installer:

```bash
~/src/cartographing-kitties-plugin/scripts/install-opencode-global.sh
```

The script:

- creates `~/.config/opencode/{skills,commands,agents}` if needed
- symlinks this repo's `.opencode/` assets into that global config directory
- adds or updates the `kitty` MCP server in `~/.config/opencode/opencode.json`

After that, OpenCode will load the `kitty` skills, commands, and subagents in any repository you open.

### OpenCode commands

- `/kitty-index`
- `/kitty-status`
- `/kitty-explore <path-or-symbol>`
- `/kitty-impact <symbol-or-path>`
- `/kitty-annotate`
- `/kitty-brainstorm <feature>`
- `/kitty-plan <feature-or-doc>`
- `/kitty-work <plan-path>`
- `/kitty-review [mode:report-only|mode:autofix]`
- `/kitty-lfg <feature>`

Skill names use OpenCode-compatible hyphenated identifiers: `kitty`, `kitty-explore`, `kitty-plan`, `kitty-review`, and so on.

## Install as Codex Plugin

This repository is now a root-level Codex plugin. The repository entrypoint manifest lives at [`.codex-plugin/plugin.json`](./.codex-plugin/plugin.json), and it reuses the existing `kitty` skills under [`plugins/kitty/skills`](./plugins/kitty/skills).

The MCP server config used by the root plugin lives at [`.mcp.json`](./.mcp.json).

### Install from Git

Clone the repository anywhere on disk:

```bash
git clone https://github.com/Kakise/cartographing-kitties-plugin.git ~/src/cartographing-kitties-plugin
```

Then point Codex at that clone as the plugin path. If you use the home-local marketplace, add this entry to `~/.agents/plugins/marketplace.json`:

```json
{
  "name": "local-plugins",
  "interface": {
    "displayName": "Local Plugins"
  },
  "plugins": [
    {
      "name": "kitty",
      "source": {
        "source": "local",
        "path": "../src/cartographing-kitties-plugin"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Developer Tools"
    }
  ]
}
```

If your Codex setup supports installing directly from a Git checkout path, use the clone root itself because `.codex-plugin/plugin.json` now exists at the repository root.

The older marketplace-ready layout under [`plugins/kitty`](./plugins/kitty) is still preserved.

## Install as Claude Code Plugin

Claude support is still preserved through [`plugins/kitty/.claude-plugin/plugin.json`](./plugins/kitty/.claude-plugin/plugin.json).

The Claude plugin layout under [`plugins/kitty`](./plugins/kitty) preserves the framework components used by Claude Code:

- `commands/`
- `skills/`
- `agents/`
- `.mcp.json`

The framework subagents remain part of the repository for both Claude Code and Codex. Their canonical declaration lives in [`plugins/kitty/agents/manifest.json`](./plugins/kitty/agents/manifest.json). In Claude Code, agents are expected to be discovered from the preserved plugin directory layout. In Codex, they are currently preserved as framework-declared components rather than a manifest-backed runtime registry.

## Install in Gemini

Gemini support is preserved through [`plugins/kitty/gemini-extension.json`](./plugins/kitty/gemini-extension.json).

## Manual installation (MCP server only)

If you only want the MCP server without the plugin framework:

```bash
pip install cartographing-kittens
# or
uvx cartographing-kittens
```

Then add to your MCP client config (`.mcp.json`):

```json
{
  "mcpServers": {
    "kitty": {
      "command": "uvx",
      "args": ["cartographing-kittens"],
      "env": {
        "KITTY_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}
```

To centralize graph storage outside the repo, add `KITTY_STORAGE_ROOT` to the same `env` block:

```json
{
  "mcpServers": {
    "kitty": {
      "command": "uvx",
      "args": ["cartographing-kittens"],
      "env": {
        "KITTY_PROJECT_ROOT": "/path/to/your/project",
        "KITTY_STORAGE_ROOT": "/path/to/kitty-storage"
      }
    }
  }
}
```

This keeps one isolated Cartograph data directory per project under the shared storage root.

## Supported Languages

| Language   | Extensions         |
| ---------- | ------------------ |
| Python     | `.py`              |
| TypeScript | `.ts`, `.tsx`      |
| JavaScript | `.js`, `.jsx`      |

## Skills

### Tool Skills — Direct Codebase Intelligence

Use these skills when you need specific structural information from the codebase.

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `kitty` | Any structural/relational question about code | Routes to the right sub-skill based on your question |
| `kitty:explore` | "What's in this file?", "How is this organized?" | Browse definitions, imports, relationships through graph traversal |
| `kitty:impact` | "What depends on X?", "What breaks if I change Y?" | Blast radius analysis with transitive dependency walking |
| `kitty:annotate` | "Enable semantic search", "Annotate the codebase" | Enrich graph nodes with summaries and domain tags |

### Workflow Skills — Engineering Pipeline

Use these skills to go from idea to shipped code with Cartographing Kittens-powered workflow orchestration.
The framework subagents remain part of the repository, but runtime behavior differs by tool:
Claude Code preserves the `agents/` layout directly, while Codex is currently inline-first and
uses the framework agent declaration in [`plugins/kitty/agents/manifest.json`](./plugins/kitty/agents/manifest.json).
The canonical cross-runtime contract lives in [`docs/architecture/codex-workflow-contract.md`](./docs/architecture/codex-workflow-contract.md).
The product vs integration boundary is documented in [`docs/architecture/repo-boundaries.md`](./docs/architecture/repo-boundaries.md).

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `kitty:brainstorm` | "Let's brainstorm", "What should we build?" | Requirements gathering from graph-backed research, inline first with optional delegation |
| `kitty:plan` | "Plan this", "How should we build this?" | Technical planning from graph-backed research, inline first with optional delegation |
| `kitty:work` | "Build this", "Implement the plan" | Execute plans with Cartographing Kittens-first workflow steps and optional delegation |
| `kitty:review` | "Review this", "Check my code" | Structural code review, inline first with optional reviewer delegation |
| `kitty:lfg` | Full autonomous mode | Chains plan, work, and review without interaction |

## How to Use the Framework

### Quick start — Explore a codebase

Just ask a structural question. The `kitty` router skill picks the right approach:

```
You: What depends on the UserService class?
→ Cartographing Kittens uses find_dependents to show all callers, importers, and subclasses

You: How is the API module organized?
→ Cartographing Kittens uses get_file_structure to show all definitions and relationships

You: Find all authentication-related code
→ Cartographing Kittens uses search (after annotation) for semantic discovery
```

### Build a feature — Full pipeline

The recommended workflow for building features:

**Step 1: Brainstorm** (optional but recommended for ambiguous features)
```
/kitty:brainstorm Add rate limiting to the API
```
Builds structural context for the target area, then uses the framework research workflow to refine requirements. Produces a requirements document.

**Step 2: Plan**
```
/kitty:plan Add rate limiting to the API
```
Produces an implementation plan with ordered units, test scenarios, and file paths. When the
runtime supports delegation cleanly, the framework may use the preserved research subagents;
otherwise the orchestrator runs inline from the same workflow contract.

**Step 3: Work**
```
/kitty:work
```
Executes the plan with Cartographing Kittens-first workflow steps. The inline-first path:
1. Calls `get_file_structure` and `query_node` on target files
2. Reads existing patterns
3. Implements following codebase conventions
4. Writes tests and verifies

Delegation remains framework-supported, but it is runtime-specific rather than guaranteed.

**Step 4: Review**
```
/kitty:review
```
Builds structural review context and applies the review workflow. The preserved reviewer subagents
remain part of the framework, but the orchestrator must still make sense in an inline execution path.

### Full autonomous mode

Skip all interaction and let Cartographing Kittens handle everything:

```
/kitty:lfg Add rate limiting to the API
```

This chains plan, work, and review from the same workflow contract. Runtime-specific delegation
may be used where available, but it is not the only execution path.

### Best Practices

1. **Index first** — Run `index_codebase` at the start of a conversation if you're unsure about graph freshness. All workflow skills do this automatically.

2. **Annotate for semantic search** — `search` works on node names by default. Run `kitty:annotate` to add summaries and tags for domain queries like "find auth code".

3. **Use impact analysis before changes** — Before modifying shared code, run `kitty:impact` or ask "what depends on X?" to understand the blast radius.

4. **Prefer the workflow contract over runtime assumptions** — delegation is useful when available, but skills must still work inline.

5. **Review with structure** — `kitty:review` finds issues that text-based reviews miss: unupdated dependents, broken contracts, circular dependencies, test coverage gaps.

## Agents

The files under [`plugins/kitty/agents`](./plugins/kitty/agents) remain first-class framework
components for both Claude Code and Codex. The runtime-neutral declaration lives in
[`plugins/kitty/agents/manifest.json`](./plugins/kitty/agents/manifest.json).

### Research Agents

Used by the framework for codebase understanding. Runtime-specific delegation is optional.

| Agent | Cat Role | Purpose |
|-------|----------|---------|
| `librarian-kitten-researcher` | Librarian Kitten | General codebase exploration — architecture, stack, modules, relationships |
| `librarian-kitten-pattern` | Librarian Kitten | Find existing patterns and conventions to follow |
| `librarian-kitten-impact` | Librarian Kitten | Blast radius and dependency chain analysis |
| `librarian-kitten-flow` | Librarian Kitten | Trace call chains and data flow through the graph |

### Review Agents (Expert Kittens)

Used by the framework for structural code review. Runtime-specific delegation is optional.

| Agent | When | Purpose |
|-------|------|---------|
| `expert-kitten-correctness` | Always | Logic errors, edge cases, state bugs |
| `expert-kitten-testing` | Always | Test coverage gaps via dependency graph |
| `expert-kitten-impact` | 3+ files changed | Blast radius — unreviewed downstream effects |
| `expert-kitten-structure` | New files created | Naming, architecture, import hygiene |

### Cartographing Kitten

| Agent | Purpose |
|-------|---------|
| `cartographing-kitten` | Batch annotation specialist — processes nodes with summaries, tags, and roles |

## MCP Tools

### Indexing

| Tool | Description |
|------|-------------|
| `index_codebase` | Parse code and build/update the graph. `full=true` for complete reindex, `full=false` for incremental. |
| `annotation_status` | Returns counts of pending, annotated, and failed nodes. |

### Search & Exploration

| Tool | Description |
|------|-------------|
| `query_node` | Look up a symbol by name. Returns the node with immediate neighbors. |
| `search` | Full-text search across names and summaries. Filter by `kind`. |
| `get_file_structure` | List all definitions in a file with relationships. |

### Dependency Analysis

| Tool | Description |
|------|-------------|
| `find_dependencies` | What does X depend on? Transitive traversal up to `max_depth` hops. |
| `find_dependents` | What depends on X? Impact analysis for change planning. |

### Annotation

| Tool | Description |
|------|-------------|
| `get_pending_annotations` | Get nodes needing annotation, with source code context. |
| `submit_annotations` | Write summaries, tags, and roles back to the graph. |

### Memory (Litter-Box & Treat-Box)

| Tool | Description |
|------|-------------|
| `add_litter_box_entry` | Record a failure, anti-pattern, or thing to avoid. Auto-exports to `.pawprints/litter-box.md`. |
| `query_litter_box` | Query negative knowledge. Filter by category, search in descriptions. |
| `add_treat_box_entry` | Record a best practice, validated pattern, or thing to always do. Auto-exports to `.pawprints/treat-box.md`. |
| `query_treat_box` | Query positive knowledge. Filter by category, search in descriptions. |

## MCP Prompts

Guided workflows that MCP clients can invoke directly:

| Prompt | Purpose |
|--------|---------|
| `explore_codebase(focus?)` | Step-by-step codebase exploration |
| `plan_refactor(target)` | Guided refactoring with blast radius analysis |
| `annotate_batch(batch_size?)` | Batch annotation workflow |

## How It Works

Cartographing Kittens builds a knowledge graph in three phases:

**Phase 1 — Parse.** Each source file is parsed with tree-sitter. The extractor walks the AST and emits `Definition`, `Import`, and `CallSite` objects.

**Phase 2 — Resolve imports.** Import statements are resolved to target files and definitions. Python module paths are converted to file paths; TypeScript/JS relative imports are resolved with extension fallback.

**Phase 3 — Resolve calls.** Call sites are matched to definitions using four strategies: `self.method()`, `imported_name()`, `qualifier.method()`, and `local_function()`.

### Graph conventions

- **Qualified names** use `::` separator: `module.path::ClassName::method_name`
- **Edge kinds**: `imports`, `calls`, `inherits`, `contains`, `depends_on`
- **Node kinds**: `module`, `class`, `function`, `method`, `variable`
- By default the graph is stored at `.pawprints/graph.db` in the project root
- If `KITTY_STORAGE_ROOT` is set, the graph and memory exports live in a per-project directory under that storage root

## Development

```bash
git clone https://github.com/Kakise/cartographing-kittens.git
cd cartographing-kittens
uv sync
```

```bash
uv run pytest              # Tests
uv run ruff check .        # Lint
uv run ruff format --check # Format check
uv run basedpyright        # Type check
uv run codespell src tests # Spell check
```

## License

MIT
