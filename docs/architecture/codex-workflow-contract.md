# Codex Workflow Contract

Cartographing Kittens supports multiple local runtimes, but they do not all expose the
same packaging and delegation primitives. This document is the canonical workflow contract
for the repository.

## Scope

- `src/cartograph/` is the product: parser, indexer, storage, annotation, MCP server, and tools.
- `plugins/kitty/` is the integration layer: commands, agent prompts, and runtime packaging.
- `plugins/kitty/skills/` is generated from `plugins/kitty/_source/skills/*.yaml`.
  See [`repo-boundaries.md`](./repo-boundaries.md) for the rules.
- `plugins/kitty/agents/*.md` remain part of the framework for both Claude Code and Codex.

## Runtime Model

| Runtime | MCP/Skills | Agent Surface | Contract |
|---|---|---|---|
| Claude Code | Preserved via `plugins/kitty/.claude-plugin/plugin.json` and plugin directory layout | `plugins/kitty/agents/` | Agents remain first-class framework components and are expected to be discovered from the plugin layout |
| Codex | Preserved via `.codex-plugin/plugin.json`, `.mcp.json`, generated skills, and prompt markdown | `plugins/kitty/.codex/agents/*.toml` | Agents are generated as Codex custom-agent TOML files with `developer_instructions` and no forced model override |

## Canonical Agent Declaration

The source of truth for framework subagents is:

- `plugins/kitty/_source/agents/*.yaml`

The generator emits both Claude markdown agents and Codex TOML agents, plus
`plugins/kitty/agents/manifest.json` as the runtime-neutral declaration.

## Delegation Model

- Primary execution mode in Codex: use generated custom-agent TOML when the task benefits
  from delegation and the runtime supports spawning that agent type.
- Inline execution remains valid for orchestrator skills and small tasks.
- Claude Code may discover and use the preserved `agents/` layout directly.
- No skill should require swarm orchestration or plugin-agent registry support in order to make sense.

## Authoring Rule

When editing README, `CLAUDE.md`, `AGENTS.md`, skills, commands, or agent prompts:

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
