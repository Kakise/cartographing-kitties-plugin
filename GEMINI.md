# Cartographing Kittens — Project Context

AST-powered codebase intelligence for AI coding agents.

## Project Overview

Cartographing Kittens is a structural intelligence framework that builds a knowledge graph of your codebase using **tree-sitter** for precise AST parsing (Python, TypeScript, JavaScript). It exposes this graph through a **Model Context Protocol (MCP)** server, enabling AI agents to perform complex structural queries (like dependency analysis and blast radius calculation) that traditional text-based tools (like grep) cannot handle.

### Key Architecture

| Layer | Component | Description |
|-------|-----------|-------------|
| **Parsing** | `src/cartograph/parsing/` | Extractors for Python, TypeScript, and JavaScript using tree-sitter. |
| **Indexing** | `src/cartograph/indexing/` | Incremental indexing and cross-file symbol resolution. |
| **Storage** | `src/cartograph/storage/` | SQLite-backed graph database with FTS5 for semantic search. |
| **Server** | `src/cartograph/server/` | FastMCP server providing tools for indexing, search, and analysis. |
| **Workflow** | `plugins/kitty/` | Shared plugin/workflow layer for Claude Code and Codex, including skills, commands, and framework subagents. |
| **Memory** | `src/cartograph/memory/` | "Litter-Box" (failures to avoid) and "Treat-Box" (validated patterns). |

## Building and Running

The project uses `uv` for dependency management and requires Python 3.11+.

### Setup & Development
- **Install Dependencies:** `uv sync --all-extras`
- **Run Tests:** `uv run pytest`
- **Linting:** `uv run ruff check .`
- **Formatting:** `uv run ruff format .`
- **Type Checking:** `uv run basedpyright`
- **Spell Check:** `uv run codespell src tests`

### Running the System
- **MCP Server (Local):** `uv run python -m cartograph.server.main` (runs via stdio)
- **Web Explorer:** `uv run kitty-graph --port 3333` (interactive graph visualization)
- **Manual Command:** `uv run cartographing-kittens` (CLI entry point)

## Development Conventions

### "Cartographing Kittens-First" Principle
When working with this codebase, prioritize using the project's own structural tools over generic text search:
- Use `get_file_structure` to understand a file's definitions and imports.
- Use `find_dependents` for impact analysis and blast radius checks.
- Use `query_node` to jump directly to symbol definitions.
- Fall back to `grep` or `glob` only for non-structural text (logs, strings, TODOs).

### Code Style & Standards
- **Qualified Names:** Symbols are indexed using `::` as a separator (e.g., `module.path::ClassName::method_name`).
- **Graph Metadata:** By default the graph is stored in `.pawprints/graph.db` within the project root.
- **Centralized Storage:** Set `KITTY_STORAGE_ROOT` to store one per-project graph directory under a shared storage root.
- **Incrementalism:** Indexing is incremental by default; only changed files are re-parsed.
- **Typing:** Strict typing is enforced via `basedpyright`. Avoid `Any` where possible.
- **Agent Contracts:**
    - Research agents (Librarian Kittens) produce structured text summaries.
    - Review agents (Expert Kittens) produce structured JSON findings.

### Workflow Skills (`kitty:*`)
The project implements a complete engineering pipeline. The framework subagents remain part of the
repository for both Claude Code and Codex, but Codex execution is currently inline-first because
the local Codex plugin manifest spec does not define an explicit `agents` field.

Canonical reference: `docs/architecture/codex-workflow-contract.md`.
Repository boundary reference: `docs/architecture/repo-boundaries.md`.

The pipeline is:
1. `kitty:brainstorm` → Requirements gathering.
2. `kitty:plan` → Technical planning from graph-backed research.
3. `kitty:work` → Execution via inline-first workflow steps with optional delegation.
4. `kitty:review` → Structural verification of changes, inline first with optional reviewer delegation.
5. `kitty:lfg` → Fully autonomous execution of the entire pipeline.

## Project Structure

- `src/cartograph/`: Core library and MCP server implementation.
- `plugins/kitty/`: Marketplace-ready Claude Code plugin definition.
- `docs/plans/`: Historical and active feature implementation plans.
- `tests/`: Comprehensive test suite (unit, e2e, and benchmark projects).
- `.pawprints/`: Default local directory for the graph database and memory logs when centralized storage is not configured.
