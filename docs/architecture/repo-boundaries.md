# Repository Boundaries

Cartographing Kittens intentionally separates product code from workflow packaging.

## Product

`src/cartograph/` is the product.

It owns:

- parsing
- indexing
- storage
- annotation
- memory
- MCP server prompts and tools

Changes here should improve the reusable code-intelligence system itself.

## Integration

`plugins/kitty/` is the integration layer.

It owns:

- Claude Code plugin packaging
- commands
- framework subagent prompts (sourced from `_source/agents/*.yaml`)
- skill content (sourced from `_source/skills/*.yaml`)
- workflow conventions

Changes here should improve how Claude Code consumes the product, not redefine the product boundary.

## Skills

`plugins/kitty/skills/` is vendored in this repository and generated from
`plugins/kitty/_source/skills/*.yaml`.

The generated skill markdown is committed so plugin consumers can install a single repository
without extra checkout steps.

It owns:

- per-skill `SKILL.md` content, frontmatter, and reference docs
- the `requires` schema and local validator that enforce each skill's runtime requirements

Rules:

- Edit `plugins/kitty/_source/skills/*.yaml`, then run
  `uv run python scripts/generate_skills.py`.
- Do not hand-edit generated `plugins/kitty/skills/*/SKILL.md` files unless you are using
  `scripts/generate_skills.py --bootstrap-from-current` as a migration helper.
- Keep generated skills and source YAML in sync with
  `uv run python scripts/generate_skills.py --check`.

## Rule of Thumb

- If a change adds or changes a reusable AST/MCP capability, it belongs in `src/cartograph/`.
- If a change alters how Claude Code invokes that capability, it belongs in
  `plugins/kitty/` or the plugin docs.
- If a change touches skill content or the skills catalog convention, edit
  `plugins/kitty/_source/skills/*.yaml` and regenerate.
- If documentation mixes the layers, prefer describing `src/cartograph/` first,
  `plugins/kitty/` second, and generated plugin artifacts third.
