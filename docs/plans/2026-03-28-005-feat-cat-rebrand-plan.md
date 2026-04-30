---
title: Cat-Themed Rebranding + Memory System + Commands
type: feat
status: complete
date: 2026-03-28
origin: docs/brainstorms/2026-03-28-003-cat-rebrand-requirements.md
implemented_in: 231a403
units:
  - id: 1
    title: Core Infrastructure (env var + data dir + FastMCP name)
    state: complete
    implemented_in: 231a403
  - id: 2
    title: Web Explorer Branding
    state: complete
    implemented_in: 231a403
  - id: 3
    title: Memory System (Litter-Box + Treat-Box)
    state: complete
    implemented_in: 231a403
  - id: 4
    title: Plugin Directory + Manifest Rename
    state: complete
    implemented_in: 231a403
  - id: 5
    title: Skill Rename
    state: complete
    implemented_in: 231a403
  - id: 6
    title: Agent Rename
    state: complete
    implemented_in: 231a403
  - id: 7
    title: Slash Commands
    state: complete
    implemented_in: 231a403
  - id: 8
    title: Documentation + Prompt Text
    state: complete
    implemented_in: 231a403
  - id: 9
    title: CI Workflows + Tests
    state: complete
    implemented_in: 231a403
---

# Cat-Themed Rebranding + Memory System + Commands — Plan

## Overview

Rebrand all user-facing surfaces from "Cartograph" to cat-themed names ("kitty", "kitten"), add litter-box/treat-box memory systems, and introduce 3 slash commands. Python internals (`src/cartograph/`, imports) remain unchanged.

## Problem Frame

The project's user-facing identity is split: some things say "Cartograph" (skills, agents, web UI, MCP server name), others already say "cartographing-kittens" (package, CLI). This plan unifies everything under the cat brand and adds two new features (memory + commands) that enhance the agent ecosystem.

## Requirements Trace

| Req | Description | Units |
|-----|-------------|-------|
| R1 | Rebrand skill names | U5 |
| R2 | Rebrand agent names | U6 |
| R3 | Rebrand plugin manifests | U4 |
| R4 | Rebrand MCP server name | U1 |
| R5 | Rebrand web explorer | U2 |
| R6 | Rebrand documentation | U8 |
| R7 | Rebrand env var + data dir | U1 |
| R8 | Litter-box memory | U3 |
| R9 | Treat-box memory | U3 |
| R10 | Slash commands | U7 |

## Scope Boundaries

**In scope**: All user-facing naming, memory system (DB + markdown), 3 commands, env var/data dir migration, docs.
**Out of scope**: Python module rename, import paths, MCP tool/prompt function names, visual assets.

## Context & Research

### Key Findings

- **467 occurrences** of "cartograph" across 73 files, but only ~38 files need changes (Python internals excluded)
- **1 test will break**: `tests/test_web.py:105` asserts `"Cartograph" in data["_html"]`
- **CI hardcodes paths**: Both `ci.yml` and `publish.yml` reference `plugins/cartograph/` — must change atomically with directory rename
- **Schema is additive**: `CREATE TABLE IF NOT EXISTS` pattern means new tables auto-create on existing databases
- **Tool registration pattern**: `@mcp.tool()` decorator + side-effect import in `main.py`
- **Memory model**: Follow annotation system pattern (dataclasses + standalone functions + `__init__.py` re-export)
- **Commands**: `.md` files with YAML frontmatter in `commands/` directory, auto-discovered by Claude Code

### Migration Strategy

For `.cartograph/` → `.pawprints/`:
1. Check if `.pawprints/` exists → use it
2. Else check if `.cartograph/` exists → `os.rename()` to `.pawprints/`
3. Else create `.pawprints/`

For env var:
```python
project_root = os.environ.get("KITTY_PROJECT_ROOT") or os.environ.get("CARTOGRAPH_PROJECT_ROOT", ".")
```

## Key Technical Decisions

1. **Centralize migration logic**: Extract a `resolve_project_paths()` helper used by all 3 entry points (MCP lifespan, `serve()`, `web/main.py:serve()`)
2. **Memory as a new package**: `src/cartograph/memory/` with `memory_store.py` + `__init__.py`, mirroring `src/cartograph/annotation/`
3. **Shared schema**: Litter-box and treat-box tables added to existing `SCHEMA_SQL` in `schema.py`
4. **Memory tools in one file**: `src/cartograph/server/tools/memory.py` with 4 tools
5. **Both dirs in exclusion list**: `EXCLUDED_DIRS` gets both `.cartograph` and `.pawprints` during transition
6. **Both dirs in .gitignore**: Keep `.cartograph/` entry alongside new `.pawprints/`

## Open Questions

None — all resolved in brainstorm phase.

---

## Implementation Units

### Unit 1: Core Infrastructure (env var + data dir + FastMCP name)

**State:** complete — implemented in 231a403

**Goal**: Migrate data directory from `.cartograph/` to `.pawprints/`, support dual env vars, rename MCP server.

**Requirements**: R4, R7

**Dependencies**: None — foundational unit.

**Files to modify**:
- `src/cartograph/server/main.py` — lifespan: migration logic, env var fallback, `FastMCP("kitty", ...)`
- `src/cartograph/__init__.py` — `serve()`: `.pawprints` path + migration
- `src/cartograph/web/main.py` — `serve()`: `.pawprints` path + migration
- `src/cartograph/indexing/discovery.py` — add `.pawprints` to `EXCLUDED_DIRS`
- `.gitignore` — add `.pawprints/`

**Approach**:
1. Create a helper function `_resolve_db_dir(project_root: str | Path) -> Path` in a new `src/cartograph/compat.py`:
   - Reads `KITTY_PROJECT_ROOT` then falls back to `CARTOGRAPH_PROJECT_ROOT` then `"."`
   - Checks for `.pawprints/` → returns it
   - Checks for `.cartograph/` → renames to `.pawprints/` → returns `.pawprints/`
   - Creates `.pawprints/` → returns it
2. Use this helper in all 3 entry points
3. Change `FastMCP("cartograph", ...)` to `FastMCP("kitty", ...)`
4. Add `.pawprints` to `EXCLUDED_DIRS` alongside `.cartograph`
5. Add `.pawprints/` to `.gitignore`

**Patterns to follow**: The current lifespan creates the dir with `mkdir(parents=True, exist_ok=True)`. Keep this pattern in the helper.

**Test scenarios**:
- Happy path: fresh project with no existing dir → `.pawprints/` created
- Migration: existing `.cartograph/` dir → renamed to `.pawprints/`, graph.db preserved
- Both exist: `.pawprints/` already exists → use it, ignore `.cartograph/`
- Env var: `KITTY_PROJECT_ROOT` takes precedence over `CARTOGRAPH_PROJECT_ROOT`
- Env var: only `CARTOGRAPH_PROJECT_ROOT` set → still works

**Verification**: `uv run pytest tests/test_stdio_e2e.py` passes; manual test: create `.cartograph/graph.db`, start server, verify it migrates to `.pawprints/graph.db`.

---

### Unit 2: Web Explorer Branding

**State:** complete — implemented in 231a403

**Goal**: Update all user-facing strings in the web explorer.

**Requirements**: R5

**Dependencies**: U1 (data dir path changes)

**Files to modify**:
- `src/cartograph/web/frontend.py` — HTML title, h1 heading, docstring
- `src/cartograph/web/server.py` — startup print message, docstring
- `src/cartograph/web/__init__.py` — docstring
- `src/cartograph/__init__.py` — argparse description string
- `tests/test_web.py` — fix assertion on line 105

**Approach**:
- `<title>Cartograph Graph Explorer</title>` → `<title>Cartographing Kittens</title>`
- `<h1>Cartograph</h1>` → `<h1>Cartographing Kittens</h1>`
- `"Cartograph Graph Explorer running at ..."` → `"Cartographing Kittens running at ..."`
- `"Interactive web explorer for the Cartograph code graph"` → `"Interactive web explorer for the Cartographing Kittens code graph"`
- `tests/test_web.py:105`: `assert "Cartograph" in data["_html"]` → `assert "Cartographing Kittens" in data["_html"]`

**Test scenarios**:
- Happy path: `test_web.py` passes with new branding string
- Edge case: HTML contains the exact new string (not partial match)

**Verification**: `uv run pytest tests/test_web.py` passes.

---

### Unit 3: Memory System (Litter-Box + Treat-Box)

**State:** complete — implemented in 231a403

**Goal**: Implement persistent memory with SQLite storage + markdown export + 4 MCP tools.

**Requirements**: R8, R9

**Dependencies**: U1 (data dir resolved to `.pawprints/`)

**Files to create**:
- `src/cartograph/memory/__init__.py` — re-exports
- `src/cartograph/memory/memory_store.py` — dataclasses + CRUD functions + markdown export

**Files to modify**:
- `src/cartograph/storage/schema.py` — add `litter_box` and `treat_box` table DDL to `SCHEMA_SQL`
- `src/cartograph/server/tools/memory.py` — 4 MCP tools (new file)
- `src/cartograph/server/main.py` — add side-effect import for `tools.memory`

**Files to create (tests)**:
- `tests/test_memory.py` — test memory module functions + markdown export

**Approach**:

**Schema** (append to `SCHEMA_SQL`):
```sql
CREATE TABLE IF NOT EXISTS litter_box (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('failure','anti-pattern','unsupported','regression','never-do')),
    description TEXT NOT NULL,
    context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    source_agent TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS treat_box (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('best-practice','validated-pattern','always-do','convention','optimization')),
    description TEXT NOT NULL,
    context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    source_agent TEXT DEFAULT ''
);
```

**Memory module** (`memory_store.py`):
```python
@dataclass
class MemoryEntry:
    id: int
    box: str  # "litter" or "treat"
    category: str
    description: str
    context: str
    created_at: str
    source_agent: str

def add_entry(store: GraphStore, box: str, category: str, description: str, context: str = "", source_agent: str = "") -> int
def query_entries(store: GraphStore, box: str, category: str | None = None, search: str | None = None, limit: int = 50) -> list[MemoryEntry]
def export_markdown(store: GraphStore, box: str, output_path: Path) -> int
```

**MCP Tools** (`tools/memory.py`):
- `add_litter_box_entry(category, description, context="", source_agent="")` → `{"id": N}`
- `query_litter_box(category=None, search=None, limit=50)` → `{"count": N, "entries": [...]}`
- `add_treat_box_entry(category, description, context="", source_agent="")` → `{"id": N}`
- `query_treat_box(category=None, search=None, limit=50)` → `{"count": N, "entries": [...]}`

**Markdown export**: Called by the MCP tools after each `add_*` to keep `.pawprints/litter-box.md` and `.pawprints/treat-box.md` in sync. Format:
```markdown
# Litter Box

## failure
- [2026-03-28] Description here (context: ..., agent: ...)

## anti-pattern
- ...
```

**Test scenarios**:
- Happy path: add entry → query returns it
- Category filter: query with specific category → only matching entries returned
- Search: query with search term → matches in description
- Markdown export: add entries → export → verify file content
- Invalid category: add entry with bad category → error returned
- Empty box: query empty box → `{"count": 0, "entries": []}`

**Verification**: `uv run pytest tests/test_memory.py tests/test_server.py` passes.

---

### Unit 4: Plugin Directory + Manifest Rename

**State:** complete — implemented in 231a403

**Goal**: Rename plugin directory tree and update manifest files.

**Requirements**: R3

**Dependencies**: None (filesystem + JSON only)

**Files to modify**:
- Rename `plugins/cartograph/` → `plugins/kitty/`
- `plugins/kitty/.claude-plugin/plugin.json` — `"name": "kitty"`, MCP server key `"kitty"`, env var `"KITTY_PROJECT_ROOT"`
- `.claude-plugin/marketplace.json` — plugin name `"kitty"`, source `"./plugins/kitty"`

**Approach**:
1. `git mv plugins/cartograph plugins/kitty`
2. Update `plugin.json`: `"name": "kitty"`, rename MCP server key from `"cartograph"` to `"kitty"`, update env to `"KITTY_PROJECT_ROOT": "."`
3. Update `marketplace.json`: `"name": "kitty"` in plugin entry, `"source": "./plugins/kitty"`

**Test scenarios**:
- Happy path: CI `validate-plugin` step can find and parse the manifest at new path
- JSON validity: both JSON files parse without error

**Verification**: `python -c "import json; json.load(open('plugins/kitty/.claude-plugin/plugin.json'))"` succeeds.

---

### Unit 5: Skill Rename

**State:** complete — implemented in 231a403

**Goal**: Rename all 9 skill directories and update skill IDs + cross-references.

**Requirements**: R1

**Dependencies**: U4 (plugin directory renamed first)

**Files to modify** (all under `plugins/kitty/skills/`):
- Rename directories: `cartograph/` → `kitty/`, `cartograph-explore/` → `kitty-explore/`, etc. (9 directories)
- Update `name:` frontmatter in all 9 `SKILL.md` files
- Update all cross-references (`cartograph:plan` → `kitty:plan`, etc.) in all SKILL.md files
- Update prose references to "Cartograph" in all SKILL.md files
- Update `plugins/kitty/skills/kitty/references/*.md` — prose references

**Approach**:
1. `git mv` each skill directory
2. In each SKILL.md: update `name:` field, replace `cartograph:` → `kitty:` in cross-refs, replace "Cartograph" → "Cartographing Kittens" in prose
3. Update reference docs in `skills/kitty/references/`

**Test scenarios**:
- All SKILL.md files have valid YAML frontmatter with `name:` starting with `kitty`
- No remaining `cartograph:` strings in any SKILL.md
- CI skill validation step passes

**Verification**: `find plugins/kitty/skills -name SKILL.md -exec grep -l 'cartograph' {} \;` returns empty.

---

### Unit 6: Agent Rename

**State:** complete — implemented in 231a403

**Goal**: Rename all 9 agent files with cat role prefixes and update all dispatch references.

**Requirements**: R2

**Dependencies**: U4 (plugin directory renamed), U5 (skill cross-refs use new agent names)

**Files to modify** (all under `plugins/kitty/agents/`):
- Rename files per mapping: `cartograph-annotator.md` → `cartographing-kitten.md`, etc.
- Update `name:` frontmatter in all 9 agent files
- Update `"reviewer":` strings in reviewer agent output contract examples
- Update agent dispatch names in SKILL.md files: `kitty-plan/SKILL.md`, `kitty-brainstorm/SKILL.md`, `kitty-review/SKILL.md`, `kitty-annotate/SKILL.md`, `kitty-work/SKILL.md`
- Update prose references to "Cartograph" in all agent files

**Agent name mapping**:

| Old file | New file | New `name:` |
|----------|----------|-------------|
| `cartograph-annotator.md` | `cartographing-kitten.md` | `cartographing-kitten` |
| `cartograph-researcher.md` | `librarian-kitten-researcher.md` | `librarian-kitten-researcher` |
| `cartograph-pattern-analyst.md` | `librarian-kitten-pattern.md` | `librarian-kitten-pattern` |
| `cartograph-impact-analyst.md` | `librarian-kitten-impact.md` | `librarian-kitten-impact` |
| `cartograph-flow-analyzer.md` | `librarian-kitten-flow.md` | `librarian-kitten-flow` |
| `cartograph-correctness-reviewer.md` | `expert-kitten-correctness.md` | `expert-kitten-correctness` |
| `cartograph-testing-reviewer.md` | `expert-kitten-testing.md` | `expert-kitten-testing` |
| `cartograph-impact-reviewer.md` | `expert-kitten-impact.md` | `expert-kitten-impact` |
| `cartograph-structure-reviewer.md` | `expert-kitten-structure.md` | `expert-kitten-structure` |

**Approach**:
1. `git mv` each agent file
2. Update `name:` field and `"reviewer":` JSON examples in each agent .md
3. Replace agent dispatch names in all SKILL.md files that reference them
4. Replace "Cartograph" prose references

**Test scenarios**:
- All agent files have valid YAML frontmatter with new names
- No remaining `cartograph-` strings in any agent file
- SKILL.md dispatch names match agent `name:` fields exactly
- CI agent validation step passes

**Verification**: `find plugins/kitty/agents -name '*.md' -exec grep -l 'cartograph' {} \;` returns empty.

---

### Unit 7: Slash Commands

**State:** complete — implemented in 231a403

**Goal**: Add 3 slash commands to the plugin.

**Requirements**: R10

**Dependencies**: U3 (memory tools exist), U4 (plugin directory at `plugins/kitty/`)

**Files to create**:
- `plugins/kitty/commands/kitty-index.md`
- `plugins/kitty/commands/kitty-explore.md`
- `plugins/kitty/commands/kitty-status.md`

**Files to modify**:
- `plugins/kitty/.claude-plugin/plugin.json` — add `"commands": "./commands"`

**Approach**:

`kitty-index.md`:
```markdown
---
description: Index or re-index the codebase graph
allowed-tools: mcp__plugin_cartograph_cartograph__index_codebase
---

Call `index_codebase` to update the code graph. If the user says "full" or "re-index", pass `full=true`. Otherwise use `full=false` for incremental indexing. Report the stats (files parsed, nodes created, edges created).
```

`kitty-explore.md`:
```markdown
---
description: Explore codebase structure using the code graph
argument-hint: [file or module path]
---

Use the Cartographing Kittens code graph to explore the structure of this codebase. $ARGUMENTS

Call `get_file_structure` on the specified path (or project root if none given). Then use `query_node` to drill into interesting symbols. Present findings as a structured overview.
```

`kitty-status.md`:
```markdown
---
description: Show index status, annotation coverage, and memory stats
---

Call `annotation_status` to get the current index and annotation state. Then call `query_litter_box` and `query_treat_box` with no filters to get entry counts. Present a summary dashboard showing:
- Files indexed and node count
- Annotation coverage percentage
- Litter-box entries (by category)
- Treat-box entries (by category)
```

**Test scenarios**:
- Happy path: each command file has valid YAML frontmatter with `description`
- Commands appear in `/help` output (manual verification)

**Verification**: `find plugins/kitty/commands -name '*.md' | wc -l` returns 3.

---

### Unit 8: Documentation + Prompt Text

**State:** complete — implemented in 231a403

**Goal**: Update all documentation and MCP prompt output text.

**Requirements**: R6

**Dependencies**: U1-U7 (all renames complete, so docs reflect final state)

**Files to modify**:
- `CLAUDE.md` — replace ~56 occurrences: skill names, agent names, data dir, env var, pipeline descriptions
- `README.md` — replace ~12 occurrences: installation, usage, tool docs
- `src/cartograph/server/prompts/explore.py` — "Cartograph's structural tools" → "Cartographing Kittens' structural tools"
- `src/cartograph/server/prompts/refactor.py` — "Cartograph's structural analysis tools" → similar
- `src/cartograph/server/prompts/annotate.py` — "Cartograph's annotation tools" → similar
- `src/cartograph/server/prompts/__init__.py` — docstring
- Various docstrings in `src/cartograph/web/`, `src/cartograph/__init__.py`

**Approach**:
1. Update CLAUDE.md: replace all skill/agent tables, update architecture section, update workflow pipeline, update development commands
2. Update README.md: replace branding in headings, installation, usage examples
3. Update prompt output strings: "Cartograph" → "Cartographing Kittens" in the 3 prompt files
4. Update docstrings that contain "Cartograph" in user-facing descriptions
5. Do NOT update docstrings that are purely about the Python module (e.g., "cartograph.storage module")

**Test scenarios**:
- `uv run pytest tests/test_prompts.py` passes (if any prompt text assertions exist)
- No user-facing string says "Cartograph" without being in a Python import context

**Verification**: `grep -r "Cartograph" src/cartograph/server/prompts/` returns only import-related lines.

---

### Unit 9: CI Workflows + Tests

**State:** complete — implemented in 231a403

**Goal**: Update CI paths and fix all test references.

**Requirements**: Supports all R1-R10.

**Dependencies**: U4 (plugin directory renamed), U1 (env var changed)

**Files to modify**:
- `.github/workflows/ci.yml` — 5 path references: `plugins/cartograph/` → `plugins/kitty/`
- `.github/workflows/publish.yml` — 1 path reference
- `tests/test_stdio_e2e.py` — env var `CARTOGRAPH_PROJECT_ROOT` → `KITTY_PROJECT_ROOT`, update comment
- `tests/test_server.py` — add new memory tools to `expected_tools` set in tool discovery test

**Approach**:
1. Replace all `plugins/cartograph` with `plugins/kitty` in CI YAMLs
2. Update `test_stdio_e2e.py`: change env var name (keep backward compat test if desired)
3. Update `test_server.py`: add `add_litter_box_entry`, `query_litter_box`, `add_treat_box_entry`, `query_treat_box` to expected tools

**Test scenarios**:
- Happy path: `uv run pytest` — full suite passes
- CI: both workflows can find plugin at new path

**Verification**: `uv run pytest` passes; `grep -r 'plugins/cartograph' .github/` returns empty.

---

## Execution Order

```
U1 (core infra) ──→ U2 (web branding) ──→ U8 (docs)
      │                                        ↑
      ├──→ U3 (memory system) ─────────────────┤
      │                                        │
      └──→ U4 (plugin dir) ──→ U5 (skills) ──→ U6 (agents) ──→ U7 (commands) ──→ U9 (CI + tests)
```

**Parallelizable**: U2, U3, and U4 can run in parallel after U1.
**Sequential gates**: U5 requires U4; U6 requires U5; U7 requires U3+U4; U8+U9 are final.

## System-Wide Impact

- **Existing users**: Anyone with `.cartograph/` directories gets auto-migrated on next server start
- **Plugin consumers**: Must reconfigure MCP server name from `cartograph` to `kitty`
- **CI**: Paths update atomically in the same commit as directory rename
- **PyPI**: Package name `cartographing-kittens` unchanged — no publishing impact

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Partial migration leaves old + new dirs | Helper checks both, prefers `.pawprints/` |
| Skill/agent name mismatch breaks dispatch | Verification grep ensures no orphan references |
| CI fails on renamed paths | CI changes in same commit as directory rename |
| Existing plugin installations break | Document migration in README changelog |

## Sources & References

- Requirements: `docs/brainstorms/2026-03-28-003-cat-rebrand-requirements.md`
- Pattern exemplar (tools): `src/cartograph/server/tools/annotate.py`
- Pattern exemplar (module): `src/cartograph/annotation/annotator.py`
- Pattern exemplar (schema): `src/cartograph/storage/schema.py`
- Pattern exemplar (tests): `tests/test_storage.py`, `tests/test_server.py`
- Claude Code command format: `.md` with YAML frontmatter in `commands/` directory
