---
title: Codex Plugin Alignment
type: refactor
status: active
date: 2026-04-21
supersedes:
  - docs/plans/2026-03-28-001-feat-ast-centric-agents-plan.md
---

# Codex Plugin Alignment — Implementation Plan

## Overview

Align the repository's plugin and workflow story with what Codex actually supports today
without deleting or demoting the framework subagents. Keep the MCP product layer stable,
preserve dual-runtime support for Claude Code and Codex, reduce overclaiming in the
workflow/docs layer, and make any agent delegation guidance explicitly Codex-native and
optional rather than assumed.

## Problem Frame

The core product in `src/cartograph/` is solid: the MCP server and tool surface are real,
modular, and already tested. The weak point is the packaging/workflow layer:

- the root Codex manifest exposes `skills` and `mcpServers`, but the local Codex manifest spec does not provide an explicit `agents` field
- `plugins/kitty/agents/*.md` exist as framework subagents, but the repo lacks a runtime-neutral declaration proving they are intentional cross-runtime components
- README and several skills describe automatic multi-agent workflows as if they were guaranteed runtime behavior
- guidance is duplicated across `README.md`, `CLAUDE.md`, `GEMINI.md`, and multiple skills, so drift is likely

The result is a mismatch between product reality and repo narrative. This plan fixes the mismatch,
preserves the subagents as part of the framework, and makes their status explicit for both runtimes
before attempting further workflow expansion.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R1. Codex-facing docs must only claim capabilities the current manifest/runtime actually exposes | Unit 1 |
| R2. The repo must have one canonical description of workflow/delegation behavior | Unit 2 |
| R3. Framework subagents must remain in the repository and be declared explicitly even where a runtime manifest lacks an `agents` field | Unit 2 |
| R4. Workflow skills must degrade cleanly to inline execution when subagents are unavailable or unnecessary | Unit 3 |
| R5. Any Codex delegation guidance must use Codex-native orchestration assumptions, not Claude-specific abstractions | Unit 3 |
| R6. Plugin packaging must be validated by tests or fixtures that check manifest/documentation consistency, including framework agent declarations | Unit 4 |
| R7. The separation between product code and plugin/workflow layer must remain explicit and minimal | Unit 5 |

## Scope Boundaries

- In scope: plugin manifests, README/internal docs, `plugins/kitty/skills/`, `plugins/kitty/agents/`, runtime-neutral agent declarations, packaging tests, small supporting docs
- Out of scope: parser/indexer/storage redesign, new MCP tools, broad feature work unrelated to Codex/plugin alignment, speculative platform support for executable custom agents

## Context & Research

### Annotation Status

- Total nodes: 899
- Annotated: 692 (77%)
- Pending: 207

### Target Nodes

- `.codex-plugin/plugin.json` — root Codex plugin manifest exposing `skills` and `mcpServers`
- `plugins/kitty/.claude-plugin/plugin.json` — preserved Claude plugin manifest exposing `commands` and `mcpServers`
- `plugins/kitty/agents/manifest.json` — runtime-neutral source of truth for framework subagents across Claude Code and Codex
- `plugins/kitty/skills/kitty-brainstorm/SKILL.md` — workflow skill that assumes named parallel agent dispatch and platform-specific question tooling
- `plugins/kitty/skills/kitty-work/SKILL.md` — workflow skill that assumes swarm mode, task teams, and persistent worker coordination
- `plugins/kitty/skills/kitty-review/SKILL.md` — richest orchestrator spec; useful as design intent, but currently more aspirational than guaranteed
- `plugins/kitty/agents/librarian-kitten-researcher.md` and peers — good prompt contracts, but not currently discoverable via the Codex manifest

### File Structures

- `src/cartograph/server/main.py` is a thin registration entrypoint importing prompts and tool modules into a single `FastMCP` server
- `src/cartograph/server/tools/query.py` contains the reusable node/context lookup primitives (`query_node`, `batch_query_nodes`, `get_context_summary`, `search`, `get_file_structure`)
- `src/cartograph/server/tools/analysis.py` contains the impact/ranking primitives (`find_dependencies`, `find_dependents`, `rank_nodes`)
- `src/cartograph/server/tools/annotate.py` contains annotation batch IO, which is already shaped for orchestrator-mediated workflows

### Importance Ranking

From the server/tool scope:

| Qualified Name | Score | Kind | Role |
|---|---|---|---|
| `cartograph.server.tools.annotate::get_pending_annotations` | 11 | function | Annotation task fetcher |
| `cartograph.server.tools.query::_summarise_node` | 10 | function | Node data formatter |
| `cartograph.server.tools.annotate::submit_annotations` | 9 | function | Annotation result submission handler |
| `cartograph.server.tools.analysis::rank_nodes` | 9 | function | |
| `cartograph.server.tools.query::batch_query_nodes` | 8 | function | Batch node structural lookup tool |
| `cartograph.server.tools.query::query_node` | 8 | function | Single node structural lookup tool |

### Dependencies and Dependents

- `cartograph.server.tools.analysis::find_dependents` depends directly on `_resolve_node` and `query::_summarise_node`
- `cartograph.server.tools.query::get_context_summary` is already a central primitive depended on by tests and adjacent tool modules, which makes it the right base for any future Codex-native orchestration

### Existing Constraints and Conventions

- The root Codex manifest currently declares only:
  - `skills: "./plugins/kitty/skills"`
  - `mcpServers: "./.mcp.json"`
- The local Codex plugin manifest spec available in this environment documents `skills`, `hooks`, `mcpServers`, and `apps`, but not an explicit `agents` field
- Official local Claude plugin examples are minimal and appear to discover `agents/` by directory convention rather than a manifest key
- The preserved Claude manifest currently declares only:
  - `commands: "./commands"`
  - inline `mcpServers`
- README currently claims a complete Codex workflow framework with agent swarms and also claims the Claude install provides “all 9 skills, and all 9 agents”, which should instead be framed around the preserved framework layout plus explicit agent declaration
- The older March plan (`2026-03-28-001`) is useful background, but it is centered on Claude/plugin-agent constraints rather than Codex manifest truth and documentation accuracy

## Key Technical Decisions

- Treat `src/cartograph/` as the product boundary and `plugins/kitty/` as a thin integration layer, not a second product
- Keep `plugins/kitty/agents/*.md` as first-class framework components for both runtimes
- Add a runtime-neutral agent declaration file so the framework explicitly declares the subagents even when a runtime manifest cannot
- Prefer inline-orchestrated workflows over mandatory delegation; delegation is an optimization, not the contract
- Keep one canonical workflow spec and derive README/internal docs from it manually or mechanically, but stop maintaining multiple independent descriptions
- Add tests around packaging/documentation consistency so the repo cannot silently regress into overclaiming again

## Open Questions

### Resolve Before Implementation

- None blocking. The repo can be improved safely by reducing claims and tightening contracts first.

### Deferred

- Whether to introduce a Codex-specific agent registry format later if/when the platform supports it cleanly
- Whether to generate README/CLAUDE/GEMINI sections from a single source document instead of maintaining them by hand

## Implementation Units

### Unit 1: Correct the Public Contract

- [x] Goal: make the public Codex/Claude installation and workflow story accurate
- Requirements: R1
- Dependencies: none
- Files:
  - modify `README.md`
  - modify `CLAUDE.md`
  - modify `GEMINI.md`
- Approach:
  - remove claims that imply agent executability or automatic swarms where the manifest/runtime does not prove that behavior
  - distinguish clearly between:
    - real product surface: MCP server + tools + skills
    - advisory workflow layer: orchestrator guidance and agent prompt contracts
  - state concretely what the Codex root plugin installs today
  - keep the preserved Claude packaging section, but reduce unsupported promises there as well
- Patterns to follow:
  - prefer exact manifest-backed language over architectural aspiration
  - preserve the repo’s “Cartographing Kittens-first” framing, but only for behaviors that are actually reachable
- Test scenarios:
  - happy path: installation sections match `.codex-plugin/plugin.json` and `plugins/kitty/.claude-plugin/plugin.json`
  - edge case: workflow docs remain useful even if no subagent execution path exists
- Verification:
  - manual diff review against both manifests
  - no doc section claims an executable feature that is not manifest-backed

### Unit 2: Establish a Canonical Workflow Spec

- [x] Goal: stop documentation drift by creating one source of truth for workflow behavior and preserve framework subagents explicitly across runtimes
- Requirements: R2, R3
- Dependencies: Unit 1
- Files:
  - create `docs/architecture/codex-workflow-contract.md`
  - create `plugins/kitty/agents/manifest.json`
  - modify `plugins/kitty/agents/*.md` frontmatter/body as needed
  - modify selected skill reference docs under `plugins/kitty/skills/kitty/references/`
- Approach:
  - define:
    - what the orchestrator skill can assume
    - what is optional delegation
    - what is fallback inline behavior
    - how Claude Code and Codex each relate to the same framework subagents
  - add a runtime-neutral `plugins/kitty/agents/manifest.json` enumerating all framework subagents
  - add a short status banner or frontmatter field to each agent markdown file clarifying its current role in the framework and any runtime-specific notes
  - have README/CLAUDE/GEMINI point to this document instead of restating the same behavioral contract in different words
- Patterns to follow:
  - keep contracts short and operational
  - prefer a single matrix/table over repeated prose
- Test scenarios:
  - happy path: a reader can answer both “is this part of the framework?” and “how is it surfaced in Codex vs Claude Code?” from one file
  - edge case: future runtime-backed agent support can be added without rewriting the whole doc structure
- Verification:
  - every framework agent appears in `plugins/kitty/agents/manifest.json`
  - every agent doc has an explicit status
  - duplicated behavioral text in README/internal docs is reduced substantially

### Unit 3: Make Workflow Skills Codex-Native and Fallback-Safe

- [x] Goal: align `brainstorm`, `plan`, `work`, `review`, and `lfg` with Codex-native orchestration and inline fallback behavior
- Requirements: R4, R5
- Dependencies: Unit 2
- Files:
  - modify `plugins/kitty/skills/kitty-brainstorm/SKILL.md`
  - modify `plugins/kitty/skills/kitty-plan/SKILL.md`
  - modify `plugins/kitty/skills/kitty-work/SKILL.md`
  - modify `plugins/kitty/skills/kitty-review/SKILL.md`
  - modify `plugins/kitty/skills/kitty-lfg/SKILL.md`
- Approach:
  - remove or rewrite platform-specific assumptions that are not portable to current Codex behavior:
    - blocking question tool requirements
    - named plugin-agent dispatch as if guaranteed
    - `TaskCreate` / agent teams / swarm mode as the default contract
  - rewrite each skill around:
    - primary mode: orchestrator executes inline using MCP tools and local code changes
    - optional mode: delegate via Codex-native subagents only when available and beneficial
  - keep the subgraph-context concept because it is architecturally sound, but present it as the orchestrator’s internal protocol rather than as proof of a guaranteed multi-agent runtime
- Patterns to follow:
  - `kitty:explore` and `kitty:impact` are closer to the right shape already: direct tool-backed workflows with clear outcomes
- Test scenarios:
  - happy path: a skill remains complete and coherent when executed inline
  - edge case: delegation-disabled or tool-limited environments still have a correct path
  - edge case: `kitty:lfg` no longer promises commit/push/PR creation as an unconditional contract
- Verification:
  - no skill requires unavailable orchestration primitives to make sense
  - skill instructions describe one executable primary path

### Unit 4: Add Packaging and Consistency Tests

- [x] Goal: enforce manifest/doc consistency in CI
- Requirements: R6
- Dependencies: Units 1-3
- Files:
  - add or modify `tests/test_plugin_packaging.py`
  - possibly extend `tests/test_prompts.py` or add a dedicated doc/manifest consistency test module
- Approach:
  - add tests that assert:
    - root Codex manifest paths exist and resolve
    - preserved Claude manifest paths exist and resolve
    - referenced skill directories exist
    - framework agent declarations in `plugins/kitty/agents/manifest.json` match the actual `plugins/kitty/agents/*.md` files
    - README installation claims do not contradict manifest structure in obvious ways
  - keep the test scope pragmatic: verify structural truth, not prose style
- Patterns to follow:
  - current server tests validate real API behavior; this unit should do the same for packaging
- Test scenarios:
  - happy path: manifests and referenced directories are in sync
  - edge case: a moved skill directory or renamed manifest fails fast in test
- Verification:
  - `uv run pytest` for the new packaging tests passes

### Unit 5: Tighten the Boundary Between Product and Integration

- [x] Goal: preserve the clean `src/cartograph/` product boundary and keep plugin logic thin
- Requirements: R7
- Dependencies: Units 1-4
- Files:
  - modify docs as needed
  - optionally add a short repo-architecture note under `docs/architecture/`
- Approach:
  - document the intended ownership split:
    - `src/cartograph/`: parser/indexer/storage/server product
    - `plugins/kitty/`: packaging, skills, optional workflow conventions
  - audit references that imply the workflow layer is the main product and rebalance them
  - explicitly bless the server tools (`query_node`, `batch_query_nodes`, `get_context_summary`, `find_dependents`, `find_dependencies`, `rank_nodes`, `get_pending_annotations`) as the stable primitives future workflow work must compose from
- Patterns to follow:
  - the current `server/main.py` + module-per-tool-area structure is the correct baseline to preserve
- Test scenarios:
  - happy path: future contributors can tell where to add product behavior vs. workflow guidance
  - edge case: new workflow features do not require broad edits to core product docs
- Verification:
  - repo docs consistently describe the same layer boundaries

## System-Wide Impact

- User-facing behavior becomes more conservative but more trustworthy
- Core MCP product remains stable
- Future Codex-native workflow work gets easier because the repo stops mixing executable contract and speculative design
- Some older docs and plans become historical rather than normative; this is intentional

## Risks & Dependencies

- Main risk: over-correcting and making the workflow story too weak or underspecified
  - mitigation: keep the design intent, but label it clearly as optional/reference until runtime-backed
- Main dependency: careful doc editing across several overlapping files
- Secondary risk: packaging tests becoming brittle if they parse prose too aggressively
  - mitigation: test only explicit structural claims and file-path invariants

## Confidence Check

Strong sections:
- problem frame
- packaging boundary
- required doc corrections

Weaker sections:
- future Codex-native delegation shape
- how much of `lfg` should remain opinionated versus minimized

Strengthening action:
- implement Units 1-3 in small passes and let packaging tests from Unit 4 harden the final contract rather than attempting a large speculative redesign first

## Sources & References

- `.codex-plugin/plugin.json`
- `plugins/kitty/.claude-plugin/plugin.json`
- `README.md`
- `CLAUDE.md`
- `GEMINI.md`
- `plugins/kitty/skills/kitty-brainstorm/SKILL.md`
- `plugins/kitty/skills/kitty-plan/SKILL.md`
- `plugins/kitty/skills/kitty-work/SKILL.md`
- `plugins/kitty/skills/kitty-review/SKILL.md`
- `plugins/kitty/skills/kitty-lfg/SKILL.md`
- `plugins/kitty/agents/*.md`
- `src/cartograph/server/main.py`
- `src/cartograph/server/tools/query.py`
- `src/cartograph/server/tools/analysis.py`
- `src/cartograph/server/tools/annotate.py`
- `docs/plans/2026-03-28-001-feat-ast-centric-agents-plan.md`
