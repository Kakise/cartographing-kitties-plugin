# AGENTS.md

## Purpose

Cartographing Kittens is an AST-powered code intelligence framework for AI coding agents. It parses Python, TypeScript, and JavaScript with tree-sitter, stores a structural graph in SQLite, and exposes that graph through an MCP server. The repo also contains a plugin workflow under `plugins/kitty/` for exploration, planning, implementation, and review.

When working in this repository, keep changes aligned with that core model:

- `src/cartograph/` is the product.
- `plugins/kitty/` is the agent/plugin packaging and workflow layer.
- `tests/` validates indexing, storage, prompts, server tools, web flows, and end-to-end behavior.

## Where To Look First

- `README.md`: public project overview and user-facing workflow.
- `CLAUDE.md` and `GEMINI.md`: concise internal architecture and workflow guidance already used by other agents.
- `pyproject.toml`: dependency, toolchain, lint, type-check, and test configuration.
- `src/cartograph/`: core implementation.
- `tests/`: expected behavior and regression coverage.

## Repo Map

- `src/cartograph/parsing/`: language extractors, query helpers, parser registry.
- `src/cartograph/indexing/`: discovery and indexing orchestration.
- `src/cartograph/storage/`: SQLite graph store, schema, migrations, connection handling.
- `src/cartograph/annotation/`: annotation pipeline.
- `src/cartograph/memory/`: persistent treat-box and litter-box memory.
- `src/cartograph/server/`: MCP server entrypoint, prompts, and tools.
- `src/cartograph/web/`: web explorer and related server/frontend wiring.
- `plugins/kitty/`: Codex/Claude plugin manifests, skills, commands, and agent definitions.
- `docs/plans/` and `docs/brainstorms/`: design history and implementation plans.
- `tests/fixtures/`: sample projects used as test inputs; treat as fixtures, not active source.

## Working Style For Agents

Prefer the project's own structural model over blind text search when possible.

- Start from the affected layer, not from broad repo-wide edits.
- Use targeted reads of the relevant modules and tests before changing code.
- Follow existing naming and architecture patterns; this project is intentionally modular by layer.
- Keep changes narrow and explicit. Avoid speculative refactors unless the task requires them.

## Project Conventions

- Qualified names use `::`, for example `package.module::ClassName::method_name`.
- The graph database lives under `.pawprints/`, typically `.pawprints/graph.db`.
- Indexing is incremental by default.
- Python 3.11+ is required.
- Ruff, BasedPyright, pytest, and codespell are the expected validation tools.
- `tests/fixtures/` should only be edited when a test scenario itself needs to change.

## Commands

Setup:

```bash
uv sync --all-extras
```

Primary validation:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv run codespell src tests
```

Run the MCP server locally:

```bash
uv run python -m cartograph.server.main
```

Run the web graph explorer:

```bash
uv run kitty-graph --port 3333
```

## Editing Guidance

- If you change parsing, indexing, storage, or graph traversal behavior, run the most relevant tests first, then broaden if needed.
- If you change MCP tools or prompts, check both implementation files under `src/cartograph/server/` and the tests that exercise them.
- If you change packaging or workflow behavior under `plugins/kitty/`, verify manifests, commands, and referenced skill/agent files stay in sync.
- Keep documentation consistent when changing public workflow, commands, or architecture assumptions.

## Testing Guidance

Start with the narrowest relevant tests:

- `tests/test_parsing.py`
- `tests/test_indexer.py`
- `tests/test_storage.py`
- `tests/test_server.py`
- `tests/test_prompts.py`
- `tests/test_web.py`
- `tests/test_e2e.py`
- `tests/test_stdio_e2e.py`

Then run the broader suite if the change affects shared behavior.

## Agent-Specific Notes

- This repository is explicitly about helping agents reason over code structure. Preserve that design bias in code and docs.
- Prefer updating tests with behavior changes rather than leaving expectations implicit.
- Avoid introducing heavyweight abstractions unless they clearly simplify one of the existing layers.
- If a change impacts both core code and plugin workflow, validate both sides of the boundary.
