---
title: Memory Workflow Enforcement
type: fix
status: complete
date: 2026-04-27
origin: docs/brainstorms/2026-03-28-003-cat-rebrand-requirements.md
implemented_in: c5d3e17
---

# Memory Workflow Enforcement Plan

## Overview

Make the litter-box and treat-box memory system unavoidable in the plugin harness.
The storage and MCP tools already exist; the failure is that skills and agents can run
for months without consulting or updating memory. This plan turns memory into a
documented, test-covered preflight and postflight contract for planning, work, review,
and delegated framework agents.

## Problem Frame

R8/R9 in the cat-rebrand requirements promised that workers and reviewers would consult
the litter box before acting, and that planning/work would consult the treat box for
positive guidance. The implementation stopped at storage, MCP tools, commands, and
status visibility. That leaves durable workflow memory passive instead of operational.

## Requirements Trace

- R8. Implement Litter-Box Memory: enforce `query_litter_box` before work/review and
  `add_litter_box_entry` after validated failures, regressions, unsupported paths, or
  anti-patterns.
- R9. Implement Treat-Box Memory: enforce `query_treat_box` before brainstorm/plan/work/review
  and `add_treat_box_entry` after validated patterns or conventions.
- R10. Add Slash Commands: keep `/kitty-status` behavior unchanged; this plan focuses on
  workflow use, not status display.

## Scope Boundaries

In scope:
- Shared memory workflow reference.
- Skill contracts for brainstorm, plan, work, review, and lfg.
- Agent contracts for all preserved framework agents.
- Subgraph context format update.
- Packaging tests that fail if memory hooks disappear.
- Dogfooding by recording one validated treat-box lesson.

Out of scope:
- Changing SQLite schema or memory categories.
- Adding semantic ranking/deduplication to memory queries.
- Commit-history derived memory entries.
- UI/web memory management.

## Context & Research

Cartographing Kittens graph status on 2026-04-27:
- Annotated: 778
- Pending: 262
- Failed: 0
- Coverage: about 75%

Search for `memory litter treat workflow skills agents` returned no semantic graph results,
which confirms this area is mostly markdown/harness text rather than indexed Python symbols.
Direct source inspection found the important surfaces:
- `src/cartograph/server/tools/memory.py` already exposes add/query MCP tools.
- `src/cartograph/memory/memory_store.py` already stores, queries, and exports entries.
- `tests/test_memory.py` and `tests/test_server.py` already cover storage/server behavior.
- `plugins/kitty/skills/*/SKILL.md` and `plugins/kitty/agents/*.md` need operational contracts.

## Memory Context

Litter lessons to avoid:
- No relevant entries currently exist.

Treat lessons to follow:
- `[validated-pattern]` Workflow skills must query litter/treat memory during preflight and
  record validated lessons during work/review postflight.
  Context: `plugins/kitty/skills/kitty/references/memory-workflow.md`;
  `tests/test_plugin_packaging.py::test_workflow_skills_require_memory_preflight`.

Memory gaps:
- This feature exposed that the boxes can remain empty unless workflows make usage explicit.

## Key Technical Decisions

- Use a shared reference file rather than duplicating full instructions in every skill.
  Rationale: one protocol can evolve while individual skills include short binding hooks.
- Make memory visible in `### Memory Context` inside subgraph context.
  Rationale: agents cannot call MCP directly in all runtimes, so orchestrators must pass memory
  alongside graph context.
- Add tests over plugin text contracts.
  Rationale: this is harness behavior, so the regression risk is removal or drift in markdown
  skill/agent definitions, not Python logic.
- Do not modify the memory database primitives.
  Rationale: the storage layer is already tested and working; the bug is unused workflow memory.

## Open Questions

### Resolve Before Work

- None. Existing categories and MCP tools are sufficient for this fix.

### Deferred

- Should memory entries gain deduplication, recency weighting, or relevance scoring?
- Should `kitty-status` report stale/unused memory health beyond raw counts?
- Should commit-history ingestion create opt-in litter/treat entries automatically?

## Implementation Units

- [ ] U1. Add shared memory workflow reference
  - Goal: Define mandatory preflight, application, postflight, categories, and output contract.
  - Requirements: R8, R9.
  - Files: `plugins/kitty/skills/kitty/references/memory-workflow.md`.
  - Approach: Describe unfiltered and filtered query protocol, when to record entries, and what final outputs must report.
  - Patterns to follow: Keep reference files concise and workflow-oriented like existing `tool-reference.md` and `subgraph-context-format.md`.
  - Test scenarios:
    - Happy path: reference mentions all four memory tools.
    - Edge: unavailable memory tools must be reported instead of silently skipped.
  - Verification: packaging test asserts the reference exists and names add/query tools.

- [ ] U2. Wire memory preflight/postflight into workflow skills
  - Goal: Ensure brainstorm/plan/work/review/lfg cannot run without explicit memory handling.
  - Requirements: R8, R9.
  - Files:
    - `plugins/kitty/skills/kitty-brainstorm/SKILL.md`
    - `plugins/kitty/skills/kitty-plan/SKILL.md`
    - `plugins/kitty/skills/kitty-work/SKILL.md`
    - `plugins/kitty/skills/kitty-review/SKILL.md`
    - `plugins/kitty/skills/kitty-lfg/SKILL.md`
    - `plugins/kitty/skills/kitty/SKILL.md`
  - Approach: Add `Memory Preflight` to read-only/research flows and `Memory Postflight` to mutating/review flows.
  - Patterns to follow: Inline-first runtime posture and optional delegation language already present in these skills.
  - Test scenarios:
    - Happy path: all workflow skills mention `query_litter_box` and `query_treat_box`.
    - Integration: mutating skills mention both add tools.
  - Verification: focused packaging tests pass.

- [ ] U3. Add Memory Context to agent and subgraph contracts
  - Goal: Make memory available to delegated agents through orchestrator-provided context.
  - Requirements: R8, R9.
  - Files:
    - `plugins/kitty/agents/*.md`
    - `plugins/kitty/skills/kitty/references/subgraph-context-format.md`
  - Approach: Add `Memory Context` to expected inputs and workflows for reviewers, researchers, pattern/flow/impact analysts, and annotation agent.
  - Patterns to follow: Agents already declare expected context and cannot assume direct MCP access.
  - Test scenarios:
    - Happy path: every framework agent includes `Memory Context` or `memory_context`.
    - Edge: annotation agent can consume memory without direct MCP access.
  - Verification: packaging test over agent definitions passes.

- [ ] U4. Expand tool reference and router skill
  - Goal: Make memory tools discoverable from the main `kitty` skill and tool reference.
  - Requirements: R8, R9.
  - Files:
    - `plugins/kitty/skills/kitty/SKILL.md`
    - `plugins/kitty/skills/kitty/references/tool-reference.md`
  - Approach: Add direct tool entries for query/add operations and update the planning/working/review heuristic.
  - Patterns to follow: Existing direct-tool table and short "when to use" guidance.
  - Test scenarios:
    - Happy path: skill docs name query/add tools and memory reference.
  - Verification: manual review plus packaging tests.

- [ ] U5. Validate and dogfood
  - Goal: Prove the memory workflow and storage still work.
  - Requirements: R8, R9.
  - Files: `tests/test_plugin_packaging.py`, `.pawprints/treat-box.md` generated by MCP export.
  - Approach: Run focused packaging checks, existing memory/server tests, and record one validated treat-box entry.
  - Test scenarios:
    - Unit: memory store tests pass.
    - Server: memory MCP tool tests pass.
    - Harness: memory-contract packaging tests pass.
  - Verification:
    - `uv run pytest tests/test_plugin_packaging.py -k 'memory or workflow_skills or mutating or framework_agents'`
    - `uv run pytest tests/test_memory.py tests/test_server.py`

## System-Wide Impact

- Skills become stateful with respect to prior lessons, reducing repeated mistakes across sessions.
- Agents remain runtime-neutral because memory is passed as structured context.
- MCP memory tools become operational workflow dependencies rather than status-only utilities.
- The plan/work/review pipeline gains an explicit final reporting obligation for memory queried, applied, and recorded.

## Risks & Dependencies

- Existing full packaging test still depends on root `.mcp.json`, which is currently deleted in the worktree. Do not conflate that unrelated packaging failure with this memory fix.
- Text-contract tests can be brittle if wording changes. Keep assertions focused on tool names and required context markers, not full prose.
- Empty litter/treat boxes should not block workflow. The correct behavior is to report memory gaps and continue.

## Sources & References

- `docs/brainstorms/2026-03-28-003-cat-rebrand-requirements.md`
- `plugins/kitty/skills/kitty/references/memory-workflow.md`
- `plugins/kitty/skills/kitty/references/subgraph-context-format.md`
- `plugins/kitty/skills/kitty/references/tool-reference.md`
- `src/cartograph/server/tools/memory.py`
- `src/cartograph/memory/memory_store.py`
- `tests/test_memory.py`
- `tests/test_server.py`
- `tests/test_plugin_packaging.py`
