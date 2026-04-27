# Skills Submodule Repository — Requirements

## Problem Frame

Cartographing Kittens currently keeps its reusable agent workflow assets inside this repository under `plugins/kitty/`. That works for the bundled Codex, Claude Code, Gemini, and OpenCode plugin layouts, but it makes the skill layer harder to publish independently and harder to reuse from tools that expect a skills catalog repository.

Create a new standalone skills repository that can be added back to this repository as a Git submodule. The new repository should be the source of truth for Cartographing Kittens skills and should also be consumable as a JetBrains AI Assistant skills repository, following the public repository shape used by `JetBrains/skills`.

## Codebase Context

The current plugin asset layout is concentrated under `plugins/kitty/`:

- `plugins/kitty/skills/` contains nine `SKILL.md`-based skills:
  `kitty`, `kitty-explore`, `kitty-impact`, `kitty-annotate`, `kitty-brainstorm`,
  `kitty-plan`, `kitty-work`, `kitty-review`, and `kitty-lfg`.
- `plugins/kitty/skills/kitty/references/` contains shared reference material used by the root `kitty` skill.
- `plugins/kitty/commands/` contains Claude-style command markdown and TOML metadata.
- `plugins/kitty/agents/` contains the reusable framework agent prompts plus `manifest.json`.
- `plugins/kitty/.codex-plugin/plugin.json` declares Codex plugin metadata and points `skills` to `./skills`.
- `plugins/kitty/.claude-plugin/plugin.json` declares Claude plugin metadata and points `commands` to `./commands`.
- `plugins/kitty/gemini-extension.json` and `plugins/kitty/.mcp.json` preserve Gemini and MCP wiring.
- `.agents/plugins/marketplace.json` points the local Codex marketplace at `./plugins/kitty`.
- `README.md` now documents that the root Codex plugin reuses the existing `plugins/kitty/skills`, while the older marketplace-ready layout under `plugins/kitty` remains preserved.

Cartographing Kittens' graph does not index Markdown or JSON packaging files, so this feature area is primarily filesystem and manifest driven rather than AST-symbol driven. The local graph is still useful for confirming that the product code and MCP implementation remain separate from the plugin packaging layer.

The JetBrains skills repository at `https://github.com/JetBrains/skills` is a public catalog-style repository: skills are stored as top-level skill directories containing `SKILL.md` and supporting files, with repository-level validation and contribution workflow around that catalog. The Cartographing Kittens skill repository should be compatible with that catalog convention while retaining Codex-compatible `SKILL.md` frontmatter.

Concrete observations from JetBrains/skills (2026-04-27):

- 127 skills; each is a hyphenated, lowercase top-level directory (e.g. `skill-creator/`, `algorithmic-art/`, `kotlin-tooling-agp9-migration/`). The Cartographing Kittens directory names already follow this shape (`kitty-explore`, `kitty-annotate`, …).
- Frontmatter is a minimal YAML block with `name`, `description`, and an optional `metadata` map containing `short-description` and `source` (URL pointing to the upstream skill). Curated skills use `metadata.source` for attribution back to authoritative repos; for skills authored here, `metadata.source` would point at the new submodule's canonical URL.
- Non-skill top-level directories are accepted: `.github/`, `.scripts/`, `doc/`, `changelog/` coexist with skill dirs without breaking discovery. This is the foothold for shipping `agents/` alongside skills as a non-skill top-level dir.
- CI runs Cisco's `skill-scanner` via `.scripts/run-skill-scanner.sh` and `.github/workflows/skill-scanner.yml`. SARIF results flow into GitHub Code Scanning.
- Skills may carry a per-skill `LICENSE.txt` and optional `agents/`, `references/`, `scripts/` subdirs.

## Requirements

- R1. Create a new standalone repository layout for Cartographing Kittens skills where each skill directory contains its own `SKILL.md` and any local references it needs.
- R2. Preserve the existing skill names, trigger intent, and workflow contracts from `plugins/kitty/skills/` unless a compatibility constraint requires a documented rename.
- R3. Make the new repository usable as a JetBrains AI Assistant skills repository by following the `JetBrains/skills` catalog convention: top-level skill directories, `SKILL.md` entrypoints, supporting files colocated with the skill, and repository-level validation metadata or scripts as needed.
- R4. Make the same repository usable by Codex plugin packaging by keeping Codex-compatible frontmatter and a stable path that can be referenced from `.codex-plugin/plugin.json`.
- R5. Convert this repository to consume the new skills repository as a Git submodule, without making `src/cartograph/` depend on the submodule at runtime.
- R6. Keep runtime-specific packaging glue separate from canonical skill content. Codex, Claude Code, Gemini, OpenCode, and MCP manifests may reference the submodule, but runtime-specific manifests should not be duplicated into every skill unless required by that runtime.
- R7. Preserve framework agents and commands either as part of the new repository or as a clearly separated companion directory inside it, with a documented rule for what belongs in `skills/`, `agents/`, and `commands/`.
- R8. Update documentation so users know which repository is authoritative for skills, how to update the submodule, and how to install the skills in Codex and JetBrains AI Assistant.
- R9. Add validation that detects missing `SKILL.md` files, broken relative references, invalid frontmatter, and stale references from manifests to moved skill paths.
- R10. Avoid changing MCP server installation semantics: `uvx cartographing-kittens` and `KITTY_PROJECT_ROOT` should continue to be the runtime path for the graph server.
- R11. The submodule ships **skills + framework agents + `agents/manifest.json`** together. The MCP server (`src/cartograph/`), Claude Code `plugin.json`, Codex plugin manifests, and runtime-specific commands (`plugins/kitty/commands/`) remain in this product repository. Skills and agents are versioned as one unit because the workflow contract (`docs/architecture/codex-workflow-contract.md`) ties them together.
- R12. Submodule layout is **flat at the root**: each skill lives at `<submodule>/<kitty-*>/SKILL.md`, matching the JetBrains/skills convention. Framework agents live at `<submodule>/agents/` as a non-skill top-level directory (alongside `.github/`, `.scripts/`, `doc/`, etc.).
- R13. Each `SKILL.md` declares a structured `requires` field in frontmatter that hosts can use to gate visibility. Minimum schema:
  ```yaml
  requires:
    mcp_servers: [kitty]            # MCP servers that must be reachable
    framework_agents: [librarian-kitten-researcher, ...]  # optional, names from agents/manifest.json
  ```
  Hosts that cannot satisfy a `requires` entry must hide the skill from invocation suggestions. The `kitty` MCP server is treated as a **hard requirement** for every skill in this catalog; the description text MUST also state this explicitly so users without the host-side `requires` filter still see it.
- R14. Each `SKILL.md` carries a `metadata.source` URL pointing at the canonical skill path inside the new submodule (the JetBrains attribution convention). When/if these skills are mirrored into `JetBrains/skills`, that catalog's entries point back to the submodule via the same field.
- R15. The skills submodule SHOULD adopt JetBrains-style CI (Cisco `skill-scanner` via GitHub Actions producing SARIF) so it stays catalog-eligible from day one. A failing scan on changed-skill error-level findings blocks the submodule's CI, not this repo's CI.
- R16. The submodule must be installable and discoverable **without** the Cartographing Kittens product checkout: a clone of the submodule alone is a valid JetBrains AI Assistant skills repository.

## Success Criteria

- The new repository can be cloned independently and exposes all existing Cartographing Kittens skills.
- This repository can point at that repository as a Git submodule and still install/load the Codex plugin from the expected plugin manifest path.
- JetBrains AI Assistant can inspect the standalone repository as a skills catalog without needing the full Cartographing Kittens product repository.
- Existing skill references such as `kitty:plan`, `kitty:review`, and `kitty:lfg` continue to resolve in Codex after the submodule transition.
- A validation command fails on broken skill paths or missing referenced files.
- After submodule init, `plugins/kitty/skills/<name>/SKILL.md` and `plugins/kitty/agents/<name>.md` both resolve to content sourced from the submodule with no manual copy step required by an end user (one `git submodule update --init --recursive` plus `uv sync` is enough).
- A host that cannot satisfy a skill's `requires` declaration (e.g. JetBrains AI Assistant without the `kitty` MCP server) hides that skill from invocation rather than offering it and failing at runtime.
- Each skill's `SKILL.md` description contains an explicit "requires Cartographing Kittens MCP server" sentence, so even hosts that ignore the `requires` field surface the dependency to the user.

## Scope Boundaries

- In scope: repository layout, submodule integration, skill file migration, manifest path updates, docs, and validation.
- In scope: deciding where existing `agents/` and `commands/` live relative to the new skill catalog.
- Out of scope: changing Cartographing Kittens MCP tools, parsing/indexing/storage behavior, or the graph database schema.
- Out of scope: publishing to JetBrains' upstream `JetBrains/skills` repository until local compatibility is proven.
- Out of scope: rewriting skill workflows beyond compatibility-preserving edits.

## Key Decisions

- **Submodule contents (resolved 2026-04-27).** Ship skills + framework agents + `agents/manifest.json` together. The MCP server, Claude Code `plugin.json`, and `commands/` stay in this repo. Rationale: skills reference framework agents by name and the workflow contract pairs them; commands are a Claude-Code-specific packaging primitive that travels with `plugin.json`.
- **Submodule layout (resolved 2026-04-27).** Flat top-level — `<submodule>/kitty-explore/`, `<submodule>/kitty-annotate/`, etc. — plus `<submodule>/agents/` as a non-skill top-level dir. This is byte-identical to the JetBrains/skills convention; existing directory names already match.
- **Host capability gating (resolved 2026-04-27).** Two-layer signal: a structured `requires` frontmatter field for hosts that honor it, **and** a hard-requirement sentence in the human-readable description for hosts that don't. The two together prevent silent runtime failures in JetBrains AI Assistant when the `kitty` MCP server isn't installed.
- **Submodule mount path in this repo (recommended).** Mount the new submodule at `plugins/kitty/skills/`. Submodule contents replace the current contents of that directory verbatim (since both already use `kitty-*` flat layout). The submodule's `agents/` subdirectory is published to `plugins/kitty/agents/` via one of two mechanisms decided in plan phase:
  - Option A (preferred if Claude Code's `plugin.json` allows it): set `"agents": "./skills/agents"` in `plugins/kitty/.claude-plugin/plugin.json` so agents are discovered from the submodule path directly. Single source of truth, zero sync step.
  - Option B (fallback): keep `plugins/kitty/agents/` as a tracked, generated directory whose contents are mirrored from `plugins/kitty/skills/agents/` by `scripts/sync-skills-agents.py` (run via `uv sync` and validated in CI). Symlinks are explicitly rejected because of cross-platform fragility.
- **Canonical skill source moves out of the product repository.** This keeps `src/cartograph/` focused on the MCP product and lets skills evolve as a reusable catalog.
- **Catalog-first layout in the new repository.** JetBrains compatibility benefits from a flat, skill-directory-oriented shape, and Codex can still consume the same `SKILL.md` files through plugin metadata.
- **Runtime manifests are adapters.** The skill content is canonical; `.codex-plugin`, `.claude-plugin`, Gemini, OpenCode, and marketplace files should only point at or package that content.
- **Submodule integration is a consumer boundary.** This repository pins a known-good skill version while the standalone skills repository releases independently.

## Open Questions

### Resolve Before Planning

- What should the new repository be named and hosted as? Candidate: `cartographing-kittens-skills` or `cartographing-kitties-skills`. (Brand alignment with the existing `cartographing-kitties-plugin` homepage URL in `plugin.json` would suggest `cartographing-kitties-skills`.)
- Does Claude Code's `.claude-plugin/plugin.json` schema accept a non-default `"agents"` path (e.g. `"./skills/agents"`)? If yes, choose Option A in the mount-path decision above; if no, plan Option B (the sync script).
- What exact JSONSchema should the `requires` frontmatter field use, and where is it validated? Candidates: a script in the submodule's `.scripts/` that runs alongside the Cisco `skill-scanner` step, plus a parallel validator in this repo's existing test suite.
- Does the submodule carry its own `LICENSE` (MIT, matching `plugin.json`) at the root, per-skill `LICENSE.txt` mirrors, or both?

### Deferred

- Whether to submit some or all skills upstream to `JetBrains/skills`.
- Whether to introduce automated release tags for skill catalog versions.
- Whether to generate runtime-specific plugin manifests from a single source metadata file.

## Sources

- Local structure: `plugins/kitty/skills/`, `plugins/kitty/.codex-plugin/plugin.json`, `plugins/kitty/.claude-plugin/plugin.json`, `plugins/kitty/agents/manifest.json`, `.agents/plugins/marketplace.json`, `README.md`.
- Public reference: `https://github.com/JetBrains/skills`.
