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
- skills
- framework subagent prompts
- workflow conventions

Changes here should improve how runtimes consume the product, not redefine the product boundary.

## Rule of Thumb

- If a change adds or changes a reusable AST/MCP capability, it belongs in `src/cartograph/`.
- If a change alters how Codex, Claude Code, Gemini, OpenCode, or another runtime invokes that capability, it belongs in `plugins/kitty/` or runtime-specific docs.
- If documentation mixes the two, prefer describing `src/cartograph/` first and `plugins/kitty/` second.
