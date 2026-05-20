# Cartographing Kittens — Skills

Canonical skills catalog for [Cartographing Kittens](https://github.com/Kakise/cartographing-kitties-plugin),
the AST-powered codebase intelligence framework for AI coding agents.

This repository ships ten skills that orchestrate Cartographing Kittens' MCP tools into
end-to-end workflows: structural exploration, impact analysis, annotation, brainstorming,
planning, implementation, review, and local Codex asset installation.

## Layout

```
.
├── kitty/                # Router skill — graph-powered codebase intelligence
│   ├── SKILL.md
│   └── references/       # Tool reference, annotation workflow, memory protocol
├── kitty-explore/        # Structural exploration
├── kitty-impact/         # Impact analysis and refactoring
├── kitty-annotate/       # Semantic annotation workflow
├── kitty-brainstorm/     # Requirements gathering
├── kitty-plan/           # Implementation planning
├── kitty-work/           # Plan execution
├── kitty-review/         # Structural code review
├── kitty-lfg/            # Autonomous plan → work → review pipeline
└── kitty-install-codex/  # Manual Codex agents/skills/prompts installer helper
```

Every top-level directory is a self-contained skill. The `kitty/` skill is the router —
the rest implement specific workflows. Sub-directories such as `kitty/references/` carry
inline documentation that the skill body references with relative paths.

## Hard requirement

Most skills in this catalog require the Cartographing Kittens MCP server. The workflow
skills orchestrate MCP tools (`index_codebase`, `query_node`, `find_dependents`, `search`,
`submit_annotations`, and related tools) and have no fallback if the server is not available.
`kitty:install-codex` is the exception because it only copies generated local assets.

Install the server:

```bash
uvx cartographing-kittens
```

The server's MCP manifest lives in the
[product repository](https://github.com/Kakise/cartographing-kitties-plugin) under
`plugins/kitty/.mcp.json`.

## Frontmatter schema

Each `SKILL.md` declares its host requirements through two layers:

1. **Structured `requires` block** — host runtimes that honor it should hide skills they
   cannot satisfy:

   ```yaml
   requires:
     mcp_servers:
       - kitty
   ```

2. **Description sentence** — MCP-backed skill descriptions end with the literal sentence
   `Requires the Cartographing Kittens MCP server (\`uvx cartographing-kittens\`).` so the
   dependency is visible even to hosts that ignore unknown frontmatter keys.

Skill markdown is generated from `plugins/kitty/_source/skills/*.yaml`.

## Consumption

### Cartographing Kittens plugin repository

The skill catalog is vendored under `plugins/kitty/skills/` and regenerated from source:

```bash
uv run python scripts/generate_skills.py
uv run python scripts/generate_skills.py --check
```

### Codex

Use `kitty:install-codex` or run:

```bash
uv run python scripts/install_codex_assets.py ~/.codex --delete-old
```

The installer copies generated Codex agents, skills, and prompt commands.

## Contributing

Skill content is authored in YAML. Edit `plugins/kitty/_source/skills/*.yaml`, regenerate
with `uv run python scripts/generate_skills.py`, and commit both the source and generated
outputs.

CI runs:
- A frontmatter validator that enforces the `requires` schema and the
  "Cartographing Kittens MCP server" sentence.

## License

MIT — see [LICENSE](./LICENSE).
