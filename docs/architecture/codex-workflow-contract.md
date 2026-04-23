# Codex Workflow Contract

Cartographing Kittens supports multiple local runtimes, but they do not all expose the
same packaging and delegation primitives. This document is the canonical workflow contract
for the repository.

## Scope

- `src/cartograph/` is the product: parser, indexer, storage, annotation, MCP server, and tools.
- `plugins/kitty/` is the integration layer: skills, commands, agent prompts, and runtime packaging.
- `plugins/kitty/agents/*.md` remain part of the framework for both Claude Code and Codex.

## Runtime Model

| Runtime | MCP/Skills | Agent Surface | Contract |
|---|---|---|---|
| Claude Code | Preserved via `plugins/kitty/.claude-plugin/plugin.json` and plugin directory layout | `plugins/kitty/agents/` | Agents remain first-class framework components and are expected to be discovered from the plugin layout |
| Codex | Preserved via `.codex-plugin/plugin.json` and `.mcp.json` | `plugins/kitty/agents/manifest.json` | Agents remain first-class framework components, but execution is inline-first because the local Codex manifest spec does not define an explicit `agents` field |

## Canonical Agent Declaration

The source of truth for framework subagents is:

- `plugins/kitty/agents/manifest.json`

This file does not replace runtime-specific discovery. It declares which subagents are part
of the framework even when a runtime manifest cannot express them directly.

## Delegation Model

- Primary execution mode in Codex: inline orchestration using MCP tools and local file edits.
- Optional execution mode in Codex: delegation when the runtime and task make it appropriate.
- Claude Code may discover and use the preserved `agents/` layout directly.
- No skill should require swarm orchestration or plugin-agent registry support in order to make sense.

## Authoring Rule

When editing README, `CLAUDE.md`, `GEMINI.md`, skills, or agent prompts:

- do not imply a runtime-backed agent registry unless the runtime manifest actually provides one
- do not remove framework subagents to “simplify” Codex support
- describe workflow delegation as runtime-specific and optional unless explicitly guaranteed

## Stable Primitives

Workflow work should compose from the existing MCP primitives rather than inventing new
repo-local abstractions:

- `query_node`
- `batch_query_nodes`
- `get_context_summary`
- `get_file_structure`
- `search`
- `find_dependents`
- `find_dependencies`
- `rank_nodes`
- `get_pending_annotations`
- `submit_annotations`
