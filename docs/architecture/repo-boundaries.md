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

- runtime packaging
- commands
- framework subagent prompts (sourced from `_source/agents/*.yaml`)
- workflow conventions

Changes here should improve how runtimes consume the product, not redefine the product boundary.

## Skills Catalog

`plugins/kitty/skills/` is a Git submodule mounted from
[`Kakise/cartographing-kitties-skills`](https://github.com/Kakise/cartographing-kitties-skills).

That repository is the canonical home for the nine `kitty:*` skills, and it doubles as a
JetBrains-AI-Assistant-compatible skills catalog.

It owns:

- per-skill `SKILL.md` content, frontmatter, and reference docs
- the `requires` schema and frontmatter validator that enforce the MCP-server dependency
- the JetBrains-style `.scripts/` and `.github/workflows/` (skill-scanner, validate)

Rules:

- Skill edits are PRs against the submodule repo, never direct edits to
  `plugins/kitty/skills/` in this product repo. Direct edits are lost on the next
  `git submodule update`.
- The submodule SHA pinned by this repo is the contract — bumping it surfaces as a
  one-line diff that explicitly references the SHA, never file contents.
- Bootstrap: `git submodule update --init --recursive` after a fresh clone.

## Rule of Thumb

- If a change adds or changes a reusable AST/MCP capability, it belongs in `src/cartograph/`.
- If a change alters how Codex, Claude Code, Gemini, OpenCode, or another runtime invokes that capability, it belongs in `plugins/kitty/` or runtime-specific docs.
- If a change touches skill content or the skills catalog convention, it belongs in the
  `Kakise/cartographing-kitties-skills` submodule repository.
- If documentation mixes the layers, prefer describing `src/cartograph/` first,
  `plugins/kitty/` second, and the skills submodule third.
