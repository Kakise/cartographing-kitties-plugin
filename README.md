# Cartographing Kittens

AST-powered codebase intelligence for AI coding agents.

Cartographing Kittens parses your code with [tree-sitter](https://tree-sitter.github.io/tree-sitter/), builds a structural graph in SQLite, and exposes it as an [MCP](https://modelcontextprotocol.io/) server. It answers questions that grep can't: *what depends on this function?*, *what breaks if I change this class?*, *show me all the auth-related code*.

It is also a **Claude Code plugin** with a complete engineering workflow framework — brainstorm, plan, implement, and review code using Cartographing Kittens-powered agent swarms.

## Install as Claude Code Plugin

**Step 1 — Add the marketplace:**

```
/plugin marketplace add Kakise/cartographing-kitties-plugin
```

**Step 2 — Install the plugin:**

```
/plugin install kitty
```

This installs the MCP server, all 9 skills, and all 9 agents. Cartographing Kittens tools become available immediately.

### Manual installation (MCP server only)

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

Use these skills to go from idea to shipped code with Cartographing Kittens-powered agent swarms.

| Skill | Trigger | What it does |
|-------|---------|--------------|
| `kitty:brainstorm` | "Let's brainstorm", "What should we build?" | Requirements gathering with parallel research agents exploring the codebase |
| `kitty:plan` | "Plan this", "How should we build this?" | Technical planning with 4 research agents analyzing patterns, dependencies, and impact |
| `kitty:work` | "Build this", "Implement the plan" | Execute plans with Cartographing Kittens-first worker swarms — each worker understands code structure before implementing |
| `kitty:review` | "Review this", "Check my code" | Multi-agent review with structural impact analysis, correctness checks, and test coverage validation |
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
Dispatches `librarian-kitten-researcher` and `librarian-kitten-pattern` in parallel to understand your codebase, then asks targeted questions to refine requirements. Produces a requirements document.

**Step 2: Plan**
```
/kitty:plan Add rate limiting to the API
```
Dispatches 4 research agents in parallel:
- **librarian-kitten-researcher** — understands architecture and technology
- **librarian-kitten-pattern** — finds existing patterns to follow
- **librarian-kitten-flow** — traces call chains in the affected area
- **librarian-kitten-impact** — assesses blast radius of proposed changes

Produces an implementation plan with ordered units, test scenarios, and file paths.

**Step 3: Work**
```
/kitty:work
```
Executes the plan with Cartographing Kittens-first worker agents. Each worker:
1. Calls `get_file_structure` and `query_node` on target files
2. Reads existing patterns
3. Implements following codebase conventions
4. Writes tests and verifies

For 3+ independent tasks, workers run as a **parallel swarm**.

**Step 4: Review**
```
/kitty:review
```
Dispatches review agents in parallel:
- **expert-kitten-correctness** (always-on) — logic errors, edge cases
- **expert-kitten-testing** (always-on) — test coverage via dependency graph
- **expert-kitten-impact** (conditional) — blast radius of changes
- **expert-kitten-structure** (conditional) — architectural consistency

Findings are merged, deduplicated, and presented by severity (P0-P3).

### Full autonomous mode

Skip all interaction and let Cartographing Kittens handle everything:

```
/kitty:lfg Add rate limiting to the API
```

This chains plan, work, and review automatically with agent swarms at every step.

### Best Practices

1. **Index first** — Run `index_codebase` at the start of a conversation if you're unsure about graph freshness. All workflow skills do this automatically.

2. **Annotate for semantic search** — `search` works on node names by default. Run `kitty:annotate` to add summaries and tags for domain queries like "find auth code".

3. **Use impact analysis before changes** — Before modifying shared code, run `kitty:impact` or ask "what depends on X?" to understand the blast radius.

4. **Let swarms do the work** — Workflow skills dispatch agents in parallel automatically. For large features, `kitty:work` runs independent implementation units simultaneously.

5. **Review with structure** — `kitty:review` finds issues that text-based reviews miss: unupdated dependents, broken contracts, circular dependencies, test coverage gaps.

## Agents

### Research Agents

Dispatched by `kitty:brainstorm` and `kitty:plan` for codebase understanding.

| Agent | Cat Role | Purpose |
|-------|----------|---------|
| `librarian-kitten-researcher` | Librarian Kitten | General codebase exploration — architecture, stack, modules, relationships |
| `librarian-kitten-pattern` | Librarian Kitten | Find existing patterns and conventions to follow |
| `librarian-kitten-impact` | Librarian Kitten | Blast radius and dependency chain analysis |
| `librarian-kitten-flow` | Librarian Kitten | Trace call chains and data flow through the graph |

### Review Agents (Expert Kittens)

Dispatched by `kitty:review` for structural code review.

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
- Graph stored at `.pawprints/graph.db` in the project root

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
