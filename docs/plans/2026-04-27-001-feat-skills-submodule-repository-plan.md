---
title: Skills Submodule Repository (JetBrains-compatible)
type: feat
status: active
date: 2026-04-27
origin: docs/brainstorms/2026-04-27-001-skills-submodule-repository-requirements.md
---

# Skills Submodule Repository — Implementation Plan

## Overview

Extract `plugins/kitty/skills/` and `plugins/kitty/agents/` into a new standalone Git
repository that doubles as a JetBrains AI Assistant–compatible skills catalog (mirroring
the layout used by `JetBrains/skills`). This product repo continues to consume the new
repo as a Git submodule mounted at `plugins/kitty/skills/`. The MCP server, plugin
manifests, and Claude Code commands stay in this repo.

## Problem Frame

Today the workflow assets (skills + framework agent prompts) live inside this product
repository. That makes them hard to publish independently and impossible for tools like
JetBrains AI Assistant to consume as a standalone catalog. The brainstorm settled on a
flat top-level submodule layout and a two-layer host-capability signal (`requires`
frontmatter + explicit description sentence). This plan turns that into concrete units.

## Requirements Trace

The brainstorm document at `docs/brainstorms/2026-04-27-001-skills-submodule-repository-requirements.md`
defines R1–R16. Mapping to units:

| Requirement | Unit |
|---|---|
| R1 (standalone repo, per-skill SKILL.md) | U1 |
| R2 (preserve names + workflow contracts) | U1 |
| R3 (JetBrains catalog convention) | U1, U2 |
| R4 (Codex `.codex-plugin` compatibility) | U3 |
| R5 (Git submodule integration; src/cartograph/ stays) | U3 |
| R6 (runtime manifests stay separate) | U3 |
| R7 (agents + commands placement rule) | U3, U5 |
| R8 (docs updated) | U5 |
| R9 (validation: missing SKILL.md, broken refs, frontmatter) | U2, U4 |
| R10 (no MCP server install change) | U3 (out-of-touch verification) |
| R11 (skills + agents + manifest.json ship together; commands stay) | U1, U3 |
| R12 (flat top-level + `agents/` non-skill dir) | U1 |
| R13 (`requires` frontmatter + hard-requirement description) | U1, U2 |
| R14 (`metadata.source` URL) | U1 |
| R15 (Cisco skill-scanner CI) | U2 |
| R16 (standalone clone is a valid catalog) | U1, U2 |

## Scope Boundaries

**In scope**
- New submodule repo bootstrap (skills + agents + manifest + LICENSE + README + CI)
- Frontmatter migration for all 9 skills (`requires`, `metadata.source`, hard-requirement sentence)
- Wiring this repo to consume the submodule at `plugins/kitty/skills/`
- Resolving how `plugins/kitty/agents/` is populated (Option A custom `agents` path vs. Option B sync script)
- Updates to `.github/workflows/ci.yml`, `.github/workflows/publish.yml`, `tests/test_plugin_packaging.py`, root docs, and architecture contracts

**Out of scope**
- Submitting any skill upstream to `JetBrains/skills` (deferred)
- Changing MCP server installation semantics (`uvx cartographing-kittens`, `KITTY_PROJECT_ROOT`)
- Restructuring `src/cartograph/`, parser, indexer, storage, or annotation
- Skill content rewrites beyond compatibility-preserving edits
- Releasing automated catalog version tags (deferred)

## Context & Research

### Current asset inventory

`plugins/kitty/skills/` (9 directories, all already use `kitty-*` flat naming that matches the JetBrains convention):
- `kitty/` — router skill, has `references/` subdir with `tool-reference.md`, `annotation-workflow.md`, `subgraph-context-format.md`
- `kitty-explore/`, `kitty-impact/`, `kitty-annotate/`
- `kitty-brainstorm/`, `kitty-plan/`, `kitty-work/`, `kitty-review/`, `kitty-lfg/`

`plugins/kitty/agents/` (9 markdown files + `manifest.json`):
- `cartographing-kitten.md` (annotation specialist)
- `librarian-kitten-{researcher,pattern,impact,flow}.md` (research)
- `expert-kitten-{correctness,testing,impact,structure}.md` (review)
- `manifest.json` declares each agent with `name`, `path`, `role`, `runtimes.{claude_code,codex}`

### Existing path references that interact with the move

Hard-coded path references discovered in this repo (must be considered in U3/U4/U5):

| Location | Reference | Sensitivity |
|---|---|---|
| `tests/test_plugin_packaging.py:15` | reads `.codex-plugin/plugin.json` then resolves `manifest["skills"]` (currently `./plugins/kitty/skills`) and `manifest["mcpServers"]` (currently `./.mcp.json`) | **High** — `.mcp.json` is currently deleted in working tree (`git status` shows `D .mcp.json`); needs reconciliation |
| `tests/test_plugin_packaging.py:21-32` | enumerates `plugins/kitty/agents/*.md` and matches against `manifest.json` paths | **High** — depends on Option A vs B |
| `.github/workflows/ci.yml:78-93` | `find plugins/kitty/skills -mindepth 1 -maxdepth 1 -type d` (count ≥ 9) and `find plugins/kitty/agents -name '*.md'` | **High** — submodule must be checked out before this runs |
| `.github/workflows/publish.yml:43` | validates `plugins/kitty/.claude-plugin/plugin.json` exists with `name`, `mcpServers` | Low — file stays in this repo |
| `.codex-plugin/plugin.json` (root) | `"skills": "./plugins/kitty/skills"`, `"mcpServers": "./.mcp.json"` | Medium — skills path unchanged after submodule mount; mcpServers path needs verification |
| `plugins/kitty/.claude-plugin/plugin.json` | `"commands": "./commands"` (no `agents` key set; agents are conventionally auto-discovered at `<plugin>/agents/`) | Medium — Option A would add `"agents": "./skills/agents"` here |
| `README.md` lines 71, 110-127, 200, 291-293 | description of plugin layout, `agents/manifest.json` boundary | Medium — wording updates |
| `AGENTS.md:30`, `GEMINI.md:17` | descriptions of `plugins/kitty/` | Low — wording updates |
| `CLAUDE.md:92` | "Codex preserves the same subagents through `plugins/kitty/agents/manifest.json`" | Low — wording update |
| `docs/architecture/repo-boundaries.md` | enumerates `plugins/kitty/` integration ownership | Medium — must articulate the submodule boundary |
| `docs/architecture/codex-workflow-contract.md` | runtime model table refers to `plugins/kitty/agents/manifest.json` | Medium — same |

### JetBrains/skills convention (confirmed 2026-04-27)

- Each skill is a flat top-level directory; minimum frontmatter is `name`, `description`, optional `metadata.short-description`, `metadata.source`. Codex consumes the same frontmatter.
- Non-skill top-level dirs are accepted alongside skills (`.github/`, `.scripts/`, `doc/`, `changelog/`). `agents/` will fit the same niche.
- `.scripts/run-skill-scanner.sh` invokes Cisco's `skill-scanner` (SARIF → GitHub Code Scanning). On change events, only changed-skill error-level findings fail CI. See https://github.com/JetBrains/skills/blob/main/.github/workflows/skill-scanner.yml.

### Cartographing Kittens graph signal

The graph is informational only here — skills and manifests are markdown/JSON, not parsed. Annotation status is 801/1023 (~78%), confirming the graph is healthy but offers no structural insight into this packaging change. The product code in `src/cartograph/` does not reference plugin paths at runtime, so R10 (no MCP behavior change) is naturally satisfied.

## Key Technical Decisions

1. **Single submodule mount at `plugins/kitty/skills/`.** The existing path is reused; submodule contents replace the directory's contents directly because both layouts are flat and use `kitty-*` naming.

2. **Agents discovery — Option A primary, Option B fallback.**
   - **Option A (preferred):** add `"agents": "./skills/agents"` to `plugins/kitty/.claude-plugin/plugin.json`. Agents are discovered from inside the submodule. Single source of truth. Requires: Claude Code's plugin schema supports a configurable `agents` path (it already supports `"commands": "./commands"`, so symmetric support is plausible but unverified). U3 includes an empirical check; if the field is ignored or fails to load, fall back to Option B without re-litigating other units.
   - **Option B (fallback):** keep `plugins/kitty/agents/` as a tracked, generated directory. A `scripts/sync-skills-agents.py` mirrors `plugins/kitty/skills/agents/*.md` and `manifest.json` into `plugins/kitty/agents/` byte-for-byte. The script runs as a `uv sync` post-install hook and a CI drift check (`git diff --exit-code plugins/kitty/agents`). Symlinks are explicitly rejected for cross-platform fragility.

3. **`requires` frontmatter schema.** Defined and validated in the submodule:
   ```yaml
   requires:
     mcp_servers:
       - kitty
     framework_agents:        # optional
       - librarian-kitten-researcher
   ```
   Hosts that honor it must hide skills they cannot satisfy. Hosts that don't (e.g. JetBrains AI Assistant if it ignores unknown keys) still surface the dependency through a sentence in `description`: every skill's description gains a "Requires the Cartographing Kittens MCP server (`uvx cartographing-kittens`)." sentence.

4. **`metadata.source` URL points at the submodule.** When the submodule is later mirrored into JetBrains/skills, mirror entries will reference back to the submodule via the same field — matching JetBrains's curation convention.

5. **Single root LICENSE in submodule.** MIT, matching the existing plugin license. Per-skill `LICENSE.txt` files are deferred unless a future skill needs a different license.

6. **Submodule name = `cartographing-kitties-skills`.** Aligns with the existing `cartographing-kitties-plugin` brand referenced in `homepage`/`repository` URLs across plugin manifests.

7. **Skill `name` field keeps the `kitty:` prefix** (e.g., `name: kitty:explore`). Reasoning: existing users invoke `/kitty:explore`; JetBrains catalogs use the `name` field for attribution rather than invocation matching, so the colon is unlikely to break catalog tooling. U2's frontmatter validator confirms this against the Cisco scanner output during the unit's verification step; if the scanner rejects the prefix, the issue is documented and reopened, not silently rebranded.

## Open Questions

### Resolve Before Implementing

- **Q1.** Does Claude Code's `.claude-plugin/plugin.json` schema accept a non-default `"agents"` path? Verify empirically in U3 by configuring `"agents": "./skills/agents"` and reloading the plugin. If unsupported, switch to Option B inside U3 — no re-plan needed.
- **Q2.** Is the root `.codex-plugin/plugin.json`'s `"mcpServers": "./.mcp.json"` reference valid given that `.mcp.json` is currently deleted at root (`git status` shows `D .mcp.json`)? U3 reconciles by either restoring `.mcp.json` at root, repointing the manifest at `plugins/kitty/.mcp.json`, or removing the field if Codex tolerates inline declarations.

### Deferred

- Submitting selected skills upstream to `JetBrains/skills` (post-validation).
- Per-skill `LICENSE.txt` overrides.
- Generating runtime-specific plugin manifests from a single source-of-truth metadata file.
- Automated semver release tags for the submodule catalog.

## Implementation Units

### U1. Bootstrap the new submodule repository

**Goal.** Create `cartographing-kitties-skills` as a standalone repo with the flat
JetBrains-compatible layout, all 9 skills migrated, all 9 framework agents migrated,
and a top-level README that documents both the JetBrains and Cartographing Kittens
consumption stories.

**Requirements advanced.** R1, R2, R3, R7, R11, R12, R13, R14, R16.

**Dependencies.** None (this is the seed). Empty new repo somewhere accessible to push.

**Files to create (in the new repo, not in this product repo):**
- `LICENSE` (MIT, copied from this repo's `LICENSE`)
- `README.md` — explains: (a) this is the canonical Cartographing Kittens skills catalog, (b) it is also a JetBrains AI Assistant–compatible skills repository, (c) install via `git submodule add` for product repo or clone-and-point for JetBrains AI Assistant, (d) every skill requires the Cartographing Kittens MCP server, (e) the `requires` frontmatter schema is documented inline.
- `kitty/SKILL.md` (+ `kitty/references/{tool-reference.md,annotation-workflow.md,subgraph-context-format.md}`) — copied verbatim from `plugins/kitty/skills/kitty/`, then frontmatter updated.
- `kitty-explore/SKILL.md`, `kitty-impact/SKILL.md`, `kitty-annotate/SKILL.md`,
  `kitty-brainstorm/SKILL.md`, `kitty-plan/SKILL.md`, `kitty-work/SKILL.md`,
  `kitty-review/SKILL.md`, `kitty-lfg/SKILL.md` — copied verbatim, frontmatter updated.
- `agents/manifest.json` — copied verbatim from `plugins/kitty/agents/manifest.json` (paths and runtime annotations remain valid because the submodule preserves the relative layout `agents/<name>.md`).
- `agents/cartographing-kitten.md`, `agents/librarian-kitten-{researcher,pattern,impact,flow}.md`, `agents/expert-kitten-{correctness,testing,impact,structure}.md` — copied verbatim.

**Approach.**
1. Create the new repo locally (`git init`, set remote to `https://github.com/Kakise/cartographing-kitties-skills`).
2. Copy `plugins/kitty/skills/<name>/` directories from this repo into the new repo's root, preserving any `references/` subdirs.
3. Copy `plugins/kitty/agents/` (including `manifest.json`) into `<new-repo>/agents/`.
4. For every `SKILL.md`, update the frontmatter:
   - Add `metadata.short-description` (the existing one-liner inside `description:`).
   - Add `metadata.source: https://github.com/Kakise/cartographing-kitties-skills/blob/main/<skill-dir>/SKILL.md`.
   - Add `requires:` block per the schema in Key Technical Decisions §3.
   - Append "Requires the Cartographing Kittens MCP server (`uvx cartographing-kittens`)." to the `description:` value (preserve the existing trigger language).
5. Write the top-level `README.md`.
6. `git add . && git commit -m "feat: bootstrap Cartographing Kittens skills catalog"`.
7. Push to remote (deferred to user — flag as a manual checkpoint at end of unit).

**Patterns to follow.**
- JetBrains/skills frontmatter shape (confirmed example: `skill-creator/SKILL.md` uses `name`, `description`, `metadata.{short-description,source}`).
- Existing Cartographing Kittens skill description style (declarative, includes trigger phrases).

**Test scenarios.**
- *Happy path:* the new repo, cloned fresh, contains 9 skill directories at the root, 1 `agents/` directory with 9 markdown files + `manifest.json`, a `LICENSE`, and a `README.md`.
- *Frontmatter invariant:* every `SKILL.md`'s `description:` contains the substring "Cartographing Kittens MCP server".
- *Frontmatter invariant:* every `SKILL.md` has a non-empty `requires.mcp_servers` array containing `kitty`.
- *Reference integrity:* relative links inside `kitty/SKILL.md` to `references/*.md` resolve from the submodule root (not the old `plugins/kitty/skills/kitty/` path).
- *Edge case:* skills that previously linked across to other skill files (none currently, but verify) preserve link targets.

**Verification.**
- `find . -mindepth 1 -maxdepth 1 -type d -exec test -f {}/SKILL.md \; -print | wc -l` returns 9.
- `python -c "import frontmatter,glob; [frontmatter.load(p) for p in glob.glob('*/SKILL.md')]"` parses every file.
- `grep -L "Cartographing Kittens MCP server" */SKILL.md` returns no matches (every skill carries the sentence).

---

### U2. Add JetBrains-compatible CI and frontmatter validator to the submodule

**Goal.** Mirror JetBrains/skills's CI posture so the submodule is catalog-eligible from
day one and so the `requires` schema is enforced on every push.

**Requirements advanced.** R3, R9, R13, R15.

**Dependencies.** U1 (the repo and content must exist).

**Files to create (in the submodule):**
- `.github/workflows/skill-scanner.yml` — runs Cisco's skill-scanner on push and PR; uploads SARIF to GitHub Code Scanning. Only changed-skill error-level findings fail CI.
- `.github/workflows/validate.yml` — runs `python .scripts/validate-frontmatter.py` on push/PR.
- `.scripts/run-skill-scanner.sh` — thin wrapper invoking `skill-scanner` with the SARIF flag (mirror JetBrains/skills's existing script as the reference implementation).
- `.scripts/validate-frontmatter.py` — Python script (stdlib + PyYAML) that walks every `*/SKILL.md`, parses frontmatter, asserts:
  - `name` is a non-empty string
  - `description` is a non-empty string containing the substring "Cartographing Kittens MCP server"
  - `metadata.source` is a string starting with `https://github.com/Kakise/cartographing-kitties-skills/`
  - `requires.mcp_servers` is a list containing at least `"kitty"`
  - if `requires.framework_agents` is present, every entry exists in `agents/manifest.json` (`agents[].name`)
  - exit non-zero on any violation; print a unified report.

**Approach.**
1. Copy JetBrains/skills's `.scripts/run-skill-scanner.sh` and `.github/workflows/skill-scanner.yml` literally; update repo-specific paths only.
2. Author `.scripts/validate-frontmatter.py` from scratch (no equivalent exists in JetBrains/skills since their `requires` field is novel here).
3. Add `validate.yml` workflow.

**Patterns to follow.**
- JetBrains/skills's `.scripts/` and `.github/workflows/` conventions.
- This product repo's CI uses `uv` and `pytest`; the submodule uses raw Python because it has no Python project — keeping dependencies minimal (PyYAML only).

**Test scenarios.**
- *Happy path:* `python .scripts/validate-frontmatter.py` exits 0 on the freshly migrated content.
- *Negative — missing requires:* delete `requires:` from one skill → exit non-zero with that skill named.
- *Negative — wrong description:* remove the "Cartographing Kittens MCP server" sentence → exit non-zero.
- *Negative — orphan framework_agent reference:* add `requires.framework_agents: [non-existent]` → exit non-zero.
- *CI integration:* PR that touches one skill triggers `skill-scanner.yml`; only that skill's findings can fail the run.

**Verification.**
- Workflow runs on a synthetic test PR and produces SARIF results visible in the GitHub Code Scanning tab.
- `validate-frontmatter.py` returns 0 on the canonical content and non-zero on each fault injection above.

---

### U3. Mount the submodule into this repo and resolve agents discovery

**Goal.** Replace this repo's in-tree `plugins/kitty/skills/` and `plugins/kitty/agents/`
with content sourced from the submodule, while keeping `plugin.json`, `commands/`, the
MCP server, and runtime manifests in place.

**Requirements advanced.** R4, R5, R6, R7, R11.

**Dependencies.** U1 (submodule repo must exist with content).

**Files to create or modify in this product repo:**
- `.gitmodules` — new entry registering the submodule:
  ```
  [submodule "plugins/kitty/skills"]
      path = plugins/kitty/skills
      url = https://github.com/Kakise/cartographing-kitties-skills.git
  ```
- `plugins/kitty/skills/` — removed from this repo's tracking (`git rm -r`) and added back as a submodule pointing at the new repo.
- `plugins/kitty/.claude-plugin/plugin.json` — Option A: add `"agents": "./skills/agents"`. Option B: leave unchanged.
- `plugins/kitty/agents/` — Option A: `git rm -r` (no longer needed). Option B: keep tracked but mark as generated (add a `.generated` sentinel or README note); rely on `scripts/sync-skills-agents.py` (created next) to keep contents in sync.
- `scripts/sync-skills-agents.py` (Option B only) — Python script that reads `plugins/kitty/skills/agents/*.md` and `manifest.json`, writes byte-identical copies to `plugins/kitty/agents/`, and exits 0 if already in sync. Run via `uv sync` post-install hook (declared in `pyproject.toml` `[tool.uv.scripts]` or a `Makefile` shim, depending on what `uv` supports cleanly).

**Approach.**
1. Cache the contents of `plugins/kitty/skills/` and `plugins/kitty/agents/` (in case Step 2 needs to be reverted).
2. `git rm -r plugins/kitty/skills` and commit; the new submodule will replace the path.
3. `git submodule add https://github.com/Kakise/cartographing-kitties-skills.git plugins/kitty/skills`.
4. **Empirical Q1 check (Option A):** edit `plugins/kitty/.claude-plugin/plugin.json` to add `"agents": "./skills/agents"`. Reload the plugin in Claude Code (manual: developer console / "Reload Plugin"). Verify the framework agents appear at their canonical names. If the schema rejects the field or the agents disappear, revert the manifest change and proceed with Option B.
5. **If Option A succeeds:** `git rm -r plugins/kitty/agents`. Update `tests/test_plugin_packaging.py` (in U4) to read from `plugins/kitty/skills/agents/`.
6. **If Option B is required:** keep `plugins/kitty/agents/` tracked. Author `scripts/sync-skills-agents.py`. Wire it into `uv sync` (or a pre-commit hook + a CI drift check). Verify sync runs idempotently.
7. Reconcile root `.codex-plugin/plugin.json`'s `"mcpServers": "./.mcp.json"` with the deleted-from-working-tree `.mcp.json` (Q2): either restore the root file or repoint the manifest. Out of strict scope for the submodule extraction but blocks CI green; resolve here so Unit U4's tests pass.

**Patterns to follow.**
- Existing `plugins/kitty/.claude-plugin/plugin.json` already declares `"commands": "./commands"` — use the same syntax shape for `"agents"`.
- Use `git submodule update --init --recursive` as the documented bootstrap command (mentioned in U5 docs).

**Test scenarios.**
- *Happy path A:* fresh clone + `git submodule update --init` populates `plugins/kitty/skills/` and (via the submodule's `agents/` subdir) makes framework agents discoverable to Claude Code at startup.
- *Happy path B:* same as A, but `plugins/kitty/agents/` is also populated by `scripts/sync-skills-agents.py` after `uv sync`; `git diff --exit-code plugins/kitty/agents` is clean.
- *Edge case — submodule not initialized:* `plugins/kitty/skills/` is empty; CI fails fast with a clear error pointing at the missing `git submodule update --init` step.
- *Edge case — submodule pin drift:* updating the submodule SHA produces a diff in this repo that explicitly references the SHA bump, never the file contents.
- *Negative — Option A misconfigured:* if `"agents": "./skills/agents"` is set but the path is empty (submodule uninit), Claude Code surfaces no framework agents → bootstrap docs (U5) cover this.

**Verification.**
- `git submodule status` lists `plugins/kitty/skills` with the expected URL.
- `find plugins/kitty/skills -mindepth 1 -maxdepth 1 -type d -exec test -f {}/SKILL.md \; -print | wc -l` returns 9.
- Option A: Claude Code "List Agents" surfaces all 9 framework agents resolved from `plugins/kitty/skills/agents/`.
- Option B: `python scripts/sync-skills-agents.py && git diff --exit-code plugins/kitty/agents` returns 0.
- Codex plugin manifest paths still resolve (`tests/test_plugin_packaging.py::test_root_codex_plugin_manifest_paths_exist`).

---

### U4. Update tests and CI in this repo for the new boundary

**Goal.** Patch the existing test suite and GitHub Actions workflows so they understand
the submodule-mounted layout and still validate the same invariants (skill count, agent
count, manifest integrity).

**Requirements advanced.** R5, R7, R9.

**Dependencies.** U3 (submodule mounted, agents discovery resolved).

**Files to modify:**
- `tests/test_plugin_packaging.py`
  - `test_agent_manifest_declares_all_framework_agents` — read agents from the resolved path:
    - Option A: `REPO_ROOT / "plugins" / "kitty" / "skills" / "agents"`
    - Option B: keep `REPO_ROOT / "plugins" / "kitty" / "agents"` as today (sync script keeps it in sync)
  - Add a new test `test_skills_submodule_initialized` — asserts `plugins/kitty/skills/.git` exists (a file in submodule mode) or the directory is non-empty with at least one `SKILL.md`.
  - Add a new test `test_skill_frontmatter_declares_requires` — for every `*/SKILL.md` under `plugins/kitty/skills/`, parse frontmatter and assert `requires.mcp_servers` contains `"kitty"`.
  - (Option B only) Add `test_agents_dir_in_sync_with_submodule` — runs `scripts/sync-skills-agents.py --check` and expects exit 0.
- `.github/workflows/ci.yml`
  - Add `submodules: recursive` to every `actions/checkout@v6` step that needs the skills/agents paths.
  - Keep the skill-count validation (`find plugins/kitty/skills ... | wc -l`) — still works because the mount path is unchanged.
  - Update the agent-count validation (`find plugins/kitty/agents ...`) to read from `plugins/kitty/skills/agents` under Option A; leave it under Option B.
- `.github/workflows/publish.yml` — add `submodules: recursive` to checkout if any publish step touches the skills/agents paths (currently it only validates `plugin.json`, but verify and adjust).
- `pyproject.toml` (Option B only) — declare `scripts/sync-skills-agents.py` as a `uv sync` post-install hook if `uv` exposes the primitive; otherwise document the manual run in the README.

**Approach.**
1. Branch off post-U3 commit.
2. Update tests one by one, running `uv run pytest tests/test_plugin_packaging.py` after each change.
3. Update CI workflows; push branch and let CI run end-to-end on the test PR.
4. Verify both happy-path checkout (with submodule) and a deliberate failure mode (CI without submodule init) produce expected outcomes.

**Patterns to follow.**
- Existing `tests/test_plugin_packaging.py` style — small, deterministic, no external network.
- Existing `ci.yml` job structure — separate `validate-plugin` job retains its purpose.

**Test scenarios.**
- *Happy path:* `uv run pytest tests/test_plugin_packaging.py` is green.
- *Negative — missing submodule:* a deliberately broken checkout (no `--init`) makes `test_skills_submodule_initialized` fail with a clear error.
- *Negative — drifting agents (Option B):* corrupt `plugins/kitty/agents/cartographing-kitten.md`; `test_agents_dir_in_sync_with_submodule` fails and points at the corrupted file.
- *Integration:* full CI run on a PR succeeds; same PR with `submodules: recursive` removed from `actions/checkout` fails fast in `validate-plugin`.

**Verification.**
- All existing tests pass (`uv run pytest`) plus the new tests.
- CI is green on a representative PR; failure modes produce actionable messages.

---

### U5. Update documentation, AGENTS/CLAUDE/GEMINI.md, and architecture contracts

**Goal.** Document where the canonical skill/agent source now lives, how to bootstrap it,
how to bump it, and what the new boundary means for runtimes and contributors.

**Requirements advanced.** R7, R8.

**Dependencies.** U3 (the boundary actually exists), U4 (CI is green).

**Files to modify:**
- `README.md` — add a "Skills Submodule" section after the existing plugin layout description (current lines 71-127). Cover: what the submodule is, why it exists, the JetBrains-AI-Assistant compatibility, and the bootstrap commands (`git submodule update --init --recursive`, `uv sync`). Update lines that describe `plugins/kitty/skills` so they note the submodule.
- `CLAUDE.md` — update the "Plugin Structure (Marketplace Layout)" tree to show `plugins/kitty/skills/` as a submodule mount and note the configurable `agents` path (Option A) or the sync script (Option B). Add a one-line link to the canonical skills repo.
- `AGENTS.md` — at line 30, append a sentence: skills + framework agents now live in the `cartographing-kitties-skills` submodule; this repository is the integration host.
- `GEMINI.md` — same update at line 17.
- `docs/architecture/repo-boundaries.md` — add a "Skills Catalog" sub-section under Integration: documents the submodule URL, the mount point, and the rule that this product repo never edits skill content directly (PRs against the submodule instead).
- `docs/architecture/codex-workflow-contract.md` — update the Runtime Model table and the Canonical Agent Declaration section so the source-of-truth path is `plugins/kitty/skills/agents/manifest.json` (Option A) or remains `plugins/kitty/agents/manifest.json` with a note that it is generated from the submodule (Option B).
- `plugins/kitty/agents/README.md` (Option B only) — short note: "This directory is generated from `plugins/kitty/skills/agents/`. Do not edit by hand. Run `python scripts/sync-skills-agents.py` to refresh."

**Approach.**
1. Draft the README "Skills Submodule" section first; it anchors the rest.
2. Walk every doc and update wording in place — do not duplicate the explanation across files; cross-reference the README.
3. Update the architecture contract last, since it is normative.

**Patterns to follow.**
- Existing CLAUDE.md "Plugin Structure" markdown table style.
- Existing `docs/architecture/repo-boundaries.md` rule-of-thumb format (Product / Integration / Rule).

**Test scenarios.**
- *Happy path:* `git diff` against pre-unit state shows updates only in the listed files.
- *Cross-reference integrity:* every link to the new submodule resolves (manual click-through during review).
- *Onboarding test:* fresh clone followed verbatim by README's bootstrap section yields a working setup (manual rehearsal).

**Verification.**
- `uv run codespell src docs README.md CLAUDE.md AGENTS.md GEMINI.md` is clean.
- `uv run ruff format --check` (if applicable) is clean (markdown is unaffected, but the repo's pre-commit hooks may include markdown linters — verify).
- A reviewer following the README from a fresh clone reproduces a green `uv run pytest`.

## System-Wide Impact

- **Code:** No `src/cartograph/` changes; `scripts/` gains one new file in Option B.
- **Tests:** `tests/test_plugin_packaging.py` extended by 1–2 tests; existing tests preserved.
- **CI:** Both workflows gain `submodules: recursive`; `validate-plugin` job is unchanged in structure but reads from a submodule-mounted path.
- **Documentation:** 6 user-facing docs touched (README, CLAUDE.md, AGENTS.md, GEMINI.md, two architecture docs).
- **Runtime behavior:** Unchanged for end users beyond the `git submodule update --init` step on first clone. The `kitty:` skills resolve at the same paths; the MCP server installs the same way.
- **External surface:** A new public repo at `https://github.com/Kakise/cartographing-kitties-skills`.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Claude Code rejects `"agents": "./skills/agents"` (Option A unsupported) | Empirical check is gated inside U3; falling back to Option B does not change other units. |
| Cisco's skill-scanner rejects the `kitty:` colon prefix in `name` | U2 verification step catches this; documented in K7 to escalate as a blocker rather than auto-rebrand. |
| Submodule pin drift: contributors update skills/agents in this repo by accident | U5 architecture contract documents the rule; pre-commit hook in U4 (Option B) detects unsynced edits; Option A makes it impossible because the path is read-only relative to this repo. |
| Root `.codex-plugin/plugin.json` references `./.mcp.json` that is deleted in working tree | Reconciled in U3 step 7; in-scope because it blocks `tests/test_plugin_packaging.py::test_root_codex_plugin_manifest_paths_exist`. |
| Cross-platform symlink fragility | Symlinks rejected by decision K2; Option B uses byte copies. |
| First-time clone confusion (skills appear empty) | U5 README explicitly documents `git submodule update --init --recursive`. |
| JetBrains AI Assistant ignores the `requires` frontmatter | Mitigated by the explicit "Cartographing Kittens MCP server" sentence appended to every description (K3). |

## Sources & References

- Origin requirements: `docs/brainstorms/2026-04-27-001-skills-submodule-repository-requirements.md`
- Architecture contracts: `docs/architecture/repo-boundaries.md`, `docs/architecture/codex-workflow-contract.md`
- Existing manifests: `plugins/kitty/.claude-plugin/plugin.json`, `plugins/kitty/.codex-plugin/plugin.json`, `plugins/kitty/gemini-extension.json`, `plugins/kitty/.mcp.json`, `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `opencode.json`
- Existing tests: `tests/test_plugin_packaging.py`
- Existing CI: `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
- JetBrains/skills (catalog convention): `https://github.com/JetBrains/skills`
- JetBrains/skills CI reference: `https://github.com/JetBrains/skills/blob/main/.github/workflows/skill-scanner.yml`
- JetBrains/skills frontmatter reference: `https://github.com/JetBrains/skills/blob/main/skill-creator/SKILL.md`
