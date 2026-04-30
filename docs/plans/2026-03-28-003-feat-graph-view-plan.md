---
title: Visual Graph View with Node Modal
type: feat
status: complete
date: 2026-03-28
implemented_in: b691992
units:
  - id: 1
    title: '`/api/graph` Backend Endpoint'
    state: complete
    implemented_in: b691992
  - id: 2
    title: Node Detail Modal
    state: complete
    implemented_in: b691992
  - id: 3
    title: Canvas Graph View
    state: complete
    implemented_in: b691992
---

# Visual Graph View — Implementation Plan

## Overview

Add a force-directed graph visualization as the main view of the web explorer, with node detail shown as a modal overlay. Disconnected components render as separate visual clusters.

## Problem Frame

The current web explorer shows nodes only as a file-tree sidebar list. There's no visual representation of the graph structure — the relationships between nodes (calls, imports, inherits, contains) are invisible until you click into a node detail. A visual graph view makes the codebase topology immediately apparent.

## Requirements

- R1. Main content area shows a canvas-based force-directed graph of nodes and edges
- R2. Nodes colored by kind using existing theme colors (purple=class, blue=function/method, green=file, orange=module, yellow=variable/interface/enum)
- R3. Disconnected components render as separate visual clusters (not overlapping)
- R4. Clicking a node (in graph or sidebar) opens a modal overlay with node detail + close button
- R5. New `/api/graph` endpoint returns nodes + edges in a single call (bulk data for graph rendering)
- R6. No external dependencies — pure Canvas API, inline in the single HTML file
- R7. Graph supports pan and zoom for navigating large codebases

## Scope Boundaries

**In scope:** Canvas graph rendering, force simulation, node modal, `/api/graph` endpoint, pan/zoom
**Out of scope:** D3/Cytoscape, WebSocket, animated transitions between views, graph editing

## Key Technical Decisions

1. **Canvas API over SVG** — better performance for hundreds of nodes; no DOM overhead
2. **Custom force simulation** — simple spring-embedder algorithm (repulsion + attraction + damping); no library needed
3. **Disconnected component detection** — BFS to find components, offset each cluster spatially
4. **Modal overlay** — `position: fixed` with backdrop; reuses the existing node detail HTML structure
5. **`/api/graph` endpoint** — returns `{nodes: [...], edges: [...]}` with configurable limit; avoids the current `/api/edges` limitation (requires filter params)

## Implementation Units

### Unit 1: `/api/graph` Backend Endpoint

**State:** complete — implemented in b691992

- [ ] **Goal:** Single API call returns all nodes and edges for graph rendering
- **Requirements:** R5
- **Dependencies:** None
- **Files:**
  - Modify: `src/cartograph/web/server.py`
  - Modify: `tests/test_web.py`
- **Approach:**
  1. Add `_api_graph` method to `GraphExplorerHandler`
  2. Accepts `?limit=300` (default 300, max 500) for node count
  3. Fetches nodes (using existing query pattern from `_api_nodes`)
  4. Fetches all edges where both `source_id` and `target_id` are in the returned node set
  5. Returns `{nodes: [...], edges: [{source_id, target_id, kind}...]}`
  6. Add route `(r"^/api/graph$", self._api_graph)` to the routes list
- **Test scenarios:**
  - Happy path: `/api/graph` returns nodes and edges with correct shape
  - Happy path: Edges only include those connecting returned nodes
  - Edge case: `/api/graph?limit=2` respects limit
- **Verification:** New `TestApiGraph` test class passes

### Unit 2: Node Detail Modal

**State:** complete — implemented in b691992

- [ ] **Goal:** Node detail appears as a modal overlay instead of replacing main content
- **Requirements:** R4
- **Dependencies:** None (can run in parallel with Unit 1)
- **Files:**
  - Modify: `src/cartograph/web/frontend.py`
- **Approach:**
  1. Add modal CSS: `.node-modal-backdrop` (fixed, full-screen, semi-transparent), `.node-modal` (centered card, max-width 700px, scrollable)
  2. Add modal HTML: empty `<div class="node-modal-backdrop" id="nodeModal">` after `#mainContent`
  3. Create `showNodeModal(id)` function — fetches `/api/nodes/${id}`, builds same HTML as current `loadNode()`, injects into modal, shows backdrop
  4. Add close button to modal header + click-outside-to-close on backdrop
  5. Update all `onclick="loadNode(...)"` calls in sidebar, search results, and neighbor list to use `showNodeModal(...)` instead
  6. Keep `loadNode()` for backwards compat but have it call `showNodeModal()`
- **Patterns to follow:** Existing `esc()`, `kindClass()`, `api()` helpers; same node detail HTML structure; `.node-modal` follows `.node-detail` naming convention
- **Test scenarios:**
  - Happy path: `GET /` still returns HTML containing "Cartograph"
  - Happy path: Modal HTML structure present in served page
- **Verification:** Frontend test still passes; manual check that modal opens/closes

### Unit 3: Canvas Graph View

**State:** complete — implemented in b691992

- [ ] **Goal:** Force-directed graph visualization in the main content area
- **Requirements:** R1, R2, R3, R6, R7
- **Dependencies:** Unit 1 (needs `/api/graph` endpoint), Unit 2 (modal for node clicks)
- **Files:**
  - Modify: `src/cartograph/web/frontend.py`
- **Approach:**

  **Canvas setup:**
  1. Replace the `.welcome` div with a `<canvas id="graphCanvas">` that fills `#mainContent`
  2. Canvas auto-sizes to container via ResizeObserver
  3. Add a small legend overlay showing kind-to-color mapping

  **Force simulation (custom, no library):**
  1. Fetch `/api/graph` on init, build node position map with random initial positions
  2. Detect disconnected components via BFS — assign each component a spatial offset so clusters don't overlap
  3. Force loop: repulsion (Coulomb's law between all node pairs), attraction (spring force along edges), centering per component, velocity damping
  4. Run simulation in `requestAnimationFrame` loop, stop when energy drops below threshold

  **Rendering:**
  1. Draw edges as lines (color by edge kind: imports=muted, calls=accent, inherits=purple, contains=green)
  2. Draw nodes as circles (radius based on edge count, color by kind using theme variables)
  3. Draw labels (node name) next to nodes, truncated if too long
  4. Highlight hovered node and its edges

  **Interaction:**
  1. Pan: mousedown + drag on empty space moves viewport
  2. Zoom: scroll wheel scales around cursor position
  3. Click node: call `showNodeModal(id)` to open detail modal
  4. Hover: highlight node + connected edges, show tooltip with qualified name
  5. Drag node: mousedown on node pins it, mousemove repositions

  **Kind-to-color map (from existing CSS):**
  - `class` → `#bc8cff` (purple)
  - `function`, `method` → `#58a6ff` (accent blue)
  - `file` → `#3fb950` (green)
  - `module` → `#f0883e` (orange)
  - `variable`, `interface`, `type_alias`, `enum` → `#d29922` (yellow)

- **Test scenarios:**
  - Happy path: `GET /` returns HTML containing `graphCanvas`
  - Happy path: Graph loads and renders nodes from `/api/graph`
- **Verification:** Manual testing — graph renders with colored nodes, edges visible, click opens modal, pan/zoom works, disconnected components separated

---

## System-Wide Impact

| Area | Impact |
|------|--------|
| `server.py` | +1 new route, +1 new method (~30 lines) |
| `frontend.py` | Major rewrite of the `FRONTEND_HTML` string — new canvas, modal, ~300+ lines of JS |
| `tests/test_web.py` | +1 new test class for `/api/graph` |
| Existing tests | No breakage — `TestFrontend` only checks for "Cartograph" string |

## Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| Canvas performance with 500+ nodes | Limit default to 300 nodes; skip labels at low zoom; spatial indexing for hit testing |
| Force simulation never converges | Energy threshold + max iteration cap (e.g., 500 ticks) |
| Large disconnected components overlap | Offset components by bounding box + padding |
| Raw string literal `r"""..."""` and JS backslashes | Test any regex in JS carefully; raw string preserves backslashes |
