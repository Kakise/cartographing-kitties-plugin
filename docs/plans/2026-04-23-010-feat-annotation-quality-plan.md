---
title: Annotation Quality Gates & Acceleration (R9)
type: feat
status: complete
date: 2026-04-23
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
parent: docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md
implemented_in: aaa393e
requirement: R9
units:
  - id: 1
    title: Quality detector
    state: complete
    implemented_in: c5d3e17
  - id: 2
    title: Requeue + MCP surface
    state: complete
    implemented_in: c5d3e17
  - id: 3
    title: Tiered routing hints
    state: complete
    implemented_in: c5d3e17
  - id: 4
    title: Dry-run integration test
    state: complete
    implemented_in: c5d3e17
  - id: 5
    title: Orchestrator prompt update
    state: complete
    implemented_in: c5d3e17
  - id: 6
    title: Documentation
    state: complete
    implemented_in: aaa393e
---

# Annotation Quality Gates — Implementation Plan (R9)

## Overview

Two-part lift to annotation quality:

1. **Detection + requeue.** Identify low-quality summaries (placeholder text, suspiciously short,
   or summaries that don't reference the node name) and re-flag them as pending so the next
   annotation pass overwrites them.
2. **Tiered annotation.** First-pass annotate obvious cases with a cheap model (local
   Haiku-equivalent or a 7B local model); escalate to a larger model only for high-centrality or
   long/complex nodes. Graph-aware cost control.

Both parts are already motivated: the brainstorm verified "Code node representing unknown"
placeholder summaries on 5+ nodes in the current graph. This plan ships gates that prevent that
pattern and a routing layer that keeps bulk annotation cheap.

## Problem Frame

The annotation orchestrator today treats every node identically and trusts whatever the LLM
returns. That produces placeholder summaries when the LLM's context is thin, and it spends
equal budget on trivial one-liner helpers and 500-line core classes. Both are fixable with a
quality-gating detector and a centrality-aware router — no change to the LLM protocol.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R9.a — Detect placeholder/low-quality summaries | Unit 1 |
| R9.b — Auto-requeue detected nodes on next `get_pending_annotations` | Unit 2 |
| R9.c — Tiered annotation routing by centrality and complexity | Unit 3 |
| R9.d — Dry-run mode for detection + routing (avoid destructive mistakes) | Unit 4 |

## Scope Boundaries

- **In scope:** heuristic quality detectors, requeue mechanism, centrality-based routing hints
  returned with pending annotation batches, dry-run reporting.
- **Out of scope:** running a local model ourselves (the orchestrator's external model is the
  contract boundary — we return *routing hints* that the agent/client honors); training or
  fine-tuning our own annotator; rewriting the annotation prompt contract.

## Context & Research

### Extension Points

- `src/cartograph/server/tools/annotate.py::find_stale_annotations` — currently detects
  content-hash drift. Extend with new quality detectors.
- `src/cartograph/server/tools/annotate.py::get_pending_annotations` — returns pending nodes to
  the orchestrator. Extend response with a `recommended_model_tier` hint per node.
- `src/cartograph/annotation/annotator.py::write_annotations` — persists annotations. Extend
  write path to re-check quality and log suspicious entries.
- `src/cartograph/annotation/quality.py` — **new module** with detectors and routing logic.

### Known Placeholder Pattern (ground truth)

The brainstorm verified: "Code node representing unknown in the system." currently present on
5+ annotated nodes. This plan must detect and requeue all of them.

## Key Technical Decisions

### Quality detectors (v1 — conservative)

A summary is **low quality** if any of:

1. **Placeholder phrase match.** Contains any of:
   `"code node representing unknown"`, `"unknown implementation"`, `"source file container"`,
   `"implementation detail"`, `"function implementation"`, `"class implementation"`.
   Detection: case-insensitive substring.
2. **Too short.** Length < 20 characters.
3. **Name-drop failure.** Summary does not contain the node's `name` (bare name, not qualified)
   OR any obvious derivation (snake_case → spaced words). Skipped for pure `file` nodes, which
   summarize the whole file.
4. **Generic-role fallback.** `role` equals `"Function"`, `"File"`, `"Class"`, `"Method"` — that
   means the annotator skipped role generation and fell back to the kind.

Any one triggers requeue. Conservative so false-positive rate is low; re-queued nodes cost only
one annotation pass.

### Requeue mechanism

- A detected node has its `annotation_status` flipped to `pending` and a new field
  `requeue_reason` populated (stored in `properties` JSON).
- Optional safety: if a node has been requeued ≥3 times, stop requeuing and surface via the
  `failed` status so the orchestrator doesn't loop.

### Tiered annotation routing

- Each pending node returned from `get_pending_annotations` includes `recommended_model_tier:
  "fast" | "strong"`.
- Routing rules (in order):
  1. If node's `centrality` (from R6) ≥ 0.5 of max → `"strong"`.
  2. Else if source length > 2000 chars → `"strong"`.
  3. Else if kind in `("class", "interface")` → `"strong"`.
  4. Otherwise → `"fast"`.
- The hint is advisory; orchestrators can ignore it (backward-compatible).
- Ships a benchmark showing cost-per-node delta once deployed (qualitative; annotation orchestrator
  owns actual spend).

## Open Questions

### Resolve Before Implementing

- **Does the orchestrator honor `recommended_model_tier`?** Recommend: orchestrator prompt update
  adds a sentence: "If the node includes `recommended_model_tier`, use it to choose between
  haiku (`fast`) and opus (`strong`)." Non-breaking.
- **Do we expose detection as a read-only tool (`find_low_quality_annotations`)?** Recommend:
  yes — lightweight, mirrors the existing `find_stale_annotations`. Users can audit without
  requeuing.

### Defer

- Learned quality scorer (small classifier model). Heuristics are good enough for the current
  placeholder rate; revisit if false positives become a complaint.

## Implementation Units

### Unit 1 — Quality detector

**State:** complete — implemented in c5d3e17

- [ ] `src/cartograph/annotation/quality.py::is_low_quality(node: dict) -> tuple[bool, list[str]]`
      — returns `(is_low, reasons)`.
- [ ] Implement the four detectors above.
- [ ] Unit tests cover each detector independently and combinations.

**Test scenarios:**
- Happy: well-formed summary → not low quality.
- Edge: each placeholder phrase → detected.
- Edge: summary of exactly 19 chars → detected; 20 chars → not detected (boundary).
- Edge: file node with no name-drop → not flagged (files get a bye).
- Edge: role "File" → flagged as generic-fallback.

### Unit 2 — Requeue + MCP surface

**State:** complete — implemented in c5d3e17

- [ ] `src/cartograph/annotation/quality.py::find_low_quality_annotations(store: GraphStore,
      limit=100) -> list[dict]` — walks annotated nodes, returns those failing `is_low_quality`
      with reasons.
- [ ] `src/cartograph/annotation/quality.py::requeue_low_quality(store, dry_run=True) -> int` —
      either dry-runs (returns count) or flips status to `pending` with a `requeue_reason`
      property.
- [ ] `src/cartograph/server/tools/annotate.py::find_low_quality_annotations` — new MCP tool
      wrapping the read path.
- [ ] `src/cartograph/server/tools/annotate.py::requeue_low_quality_annotations(dry_run: bool =
      True)` — new MCP tool wrapping the write path.
- [ ] Register both in `server/main.py`.

**Files:** `src/cartograph/annotation/quality.py` (new),
`src/cartograph/server/tools/annotate.py` (modify),
`src/cartograph/server/main.py` (modify).

**Test scenarios:**
- Happy: fixture with 5 placeholder summaries → `find_low_quality_annotations` returns all 5
  with reasons.
- Happy: `requeue_low_quality(dry_run=False)` flips their status; `annotation_status()` now
  reports 5 pending.
- Edge: node already requeued 3 times → surfaced via return value but **not** requeued again.
  Its status flips to `failed` so the orchestrator skips it.

### Unit 3 — Tiered routing hints

**State:** complete — implemented in c5d3e17

- [ ] Extend `get_pending_annotations` to include `recommended_model_tier` per returned node.
- [ ] Routing logic in `quality.py::recommended_tier(node: dict) -> Literal["fast", "strong"]`.
- [ ] If R6 (centrality) hasn't shipped, fall back to size + kind rules only; tier field is still
      returned.

**Files:** `src/cartograph/annotation/quality.py` (extend),
`src/cartograph/server/tools/annotate.py::get_pending_annotations` (modify).

**Test scenarios:**
- Happy: small free function → `"fast"`.
- Happy: top-centrality class → `"strong"`.
- Happy: long function body (3000 chars) → `"strong"`.
- Edge: centrality NULL (R6 not applied) → size/kind rules used; no crash.

### Unit 4 — Dry-run integration test

**State:** complete — implemented in c5d3e17

- [ ] `tests/test_annotation_quality.py` — end-to-end: seed a DB with 10 mixed-quality nodes,
      call `find_low_quality_annotations` → assert reasons; call `requeue_low_quality(dry_run=
      True)` → assert no DB mutation; `requeue_low_quality(dry_run=False)` → assert mutation.
- [ ] Include a regression fixture based on the 5+ real placeholder summaries present in the
      current repo.

### Unit 5 — Orchestrator prompt update

**State:** complete — implemented in c5d3e17

- [ ] Update the annotation-orchestrator agent(s) documentation (likely
      `plugins/kitty/agents/cartographing-kitten.md` if that's where annotation guidance lives;
      or `plugins/kitty/skills/kitty-annotate/SKILL.md`) to mention:
      - Always honor `recommended_model_tier` when provided.
      - Treat requeued nodes (visible via `requeue_reason`) with extra care — the previous
        summary was inadequate, so the new one must address the specific `requeue_reason`.

**Files:** `plugins/kitty/agents/cartographing-kitten.md`,
`plugins/kitty/skills/kitty-annotate/SKILL.md` (modify as appropriate — confirm exact file in
implementation).

### Unit 6 — Documentation

**State:** complete — implemented in aaa393e

- [ ] Update `README.md` annotation section.
- [ ] Update `CLAUDE.md` tool list.
- [ ] Update `plugins/kitty/skills/kitty/references/tool-reference.md`.
- [ ] Update `plugins/kitty/skills/kitty/references/annotation-workflow.md` to describe the
      quality gate as part of the workflow.

## System-Wide Impact

- **Plugin surface:** +2 MCP tools (find + requeue).
- **Orchestrator cost:** tiered routing reduces per-pass cost when `fast` tier is honored — a
  non-trivial win at bulk scale. Orchestrator owners see the routing hint in their input.
- **Agent behavior:** the annotation orchestrator is the one affected agent; the prompt update
  in Unit 5 is the behavior change.
- **Existing graph:** on first run of `requeue_low_quality(dry_run=False)`, the 5+ known
  placeholder nodes flip to pending. Next annotation pass fixes them.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| False positives requeue genuinely good summaries | Conservative detectors + dry-run default + requeue cap of 3 |
| Tiered routing wastes budget on "strong" nodes that aren't structurally important | Centrality gate (R6) is the right signal when available; size + kind are the fallback |
| Detection rules miss new placeholder phrases as models drift | Placeholder phrase list is a module constant — easy to add to |
| Requeue loop if the underlying prompt can't improve the summary | Requeue cap + final `failed` status after 3 loops |

**Dependencies:** benefits from **R6** (centrality) for the strongest routing signal. Without R6,
size + kind rules apply. Not a blocker.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R9)
- Parent roadmap: `docs/plans/2026-04-23-001-feat-plugin-evolution-roadmap.md`

## Handoff

Ready for `kitty:work`. Smallest after R6. Entry point: Unit 1 (detectors). Units 2–3
sequential. Unit 4 is the test gate. Units 5–6 are prompt + docs updates.
