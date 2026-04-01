---
title: Nested Box Treemap Graph Explorer
type: feat
status: active
date: 2026-03-28
origin: docs/brainstorms/2026-03-28-002-nested-box-graph-explorer-requirements.md
---

# Nested Box Treemap Graph Explorer — Implementation Plan

## Overview

Replace the current 3-level drill-down web explorer with a single-canvas nested treemap view. Directories are rendered as nested boxes containing file boxes containing node graphs, all on one zoomable canvas. Cross-box relationships are shown as curved bezier edges. Semantic zoom switches between compact dot grids (zoomed out) and force-directed graphs (zoomed in) per file box.

## Problem Frame

The current drill-down view (directory cards → file cards → per-file graph) hides cross-module relationships and loses spatial context when navigating. The user wants to see the entire codebase structure at a glance and zoom into any area for detail, while still seeing how modules connect to each other.

## Requirements Trace

| Req | Unit |
|-----|------|
| R1 (recursive nested boxes) | U2, U3 |
| R2 (squarified treemap) | U2 |
| R3 (dynamic box sizing) | U2 |
| R4 (header labels) | U3 |
| R5 (compact dot grid) | U4 |
| R6 (force-directed when zoomed) | U4 |
| R7 (smooth transition) | U4 |
| R8 (curved bezier edges) | U5 |
| R9 (cross-box edges visible) | U5 |
| R10 (edge bundling) | U5 |
| R11 (pan and zoom) | U6 (existing, preserve) |
| R12 (click node → modal) | U6 (existing, preserve) |
| R13 (hover highlights) | U6 |
| R14 (click box header to focus) | U6 |
| R15 (new /api/tree) | U1 |
| R16 (full graph load) | U1 |

## Scope Boundaries

**In scope:** Treemap layout, semantic zoom, bezier edges, edge bundling, box-focus navigation, /api/tree endpoint, full-graph loading.

**Out of scope:** Collapsible boxes, edge routing around boxes, minimap, WebGL, saving view state.

## Context & Research

- **Blast radius: LOW.** Web module is a leaf — no MCP tools, parsers, or indexers depend on it.
- **Files to modify:** `frontend.py` (rewrite FRONTEND_HTML), `server.py` (add endpoint + modify limit), `test_web.py` (add/update tests).
- **Reusable patterns:** Camera model (camX/camY/camZoom), screenToWorld/hitTest, roundRect, KIND_COLORS/EDGE_COLORS, node modal, sidebar, search overlay, HiDPI canvas sizing.
- **Replace:** 3-level navigation state machine, HTML card views (dir-grid, file-grid), buildGroups() wrapping grid, straight-line edge rendering.
- **Performance:** 700 nodes + 1000 edges is fine for Canvas 2D. Per-file force sims only run for visible zoomed-in boxes (~5-10 simultaneously).

## Key Technical Decisions

1. **Squarified treemap algorithm** — deterministic, no-overlap layout. Implemented inline in JS (~60 lines). Sizes boxes by recursive node count.
2. **Semantic zoom threshold: 200px screen-space** — below this, file boxes render as dot grids. Above, they render as force-directed graphs.
3. **Per-file mini-simulations** — each file box in graph mode gets its own force sim instance with fixed bounds (no elastic groups). Only active for boxes currently in graph mode.
4. **Edge bundling** — multiple edges between the same two file boxes are merged into a single bezier curve with a count label. Reduces visual noise from O(edges) to O(unique file pairs).
5. **Tree data from single SQL query** — `SELECT file_path, COUNT(*) FROM nodes WHERE kind != 'file' GROUP BY file_path`, then build tree in Python. No schema changes.

## Open Questions

None blocking. Deferred: deep nesting collapse (4+ levels), manual zoom-threshold slider.

---

## Implementation Units

### Unit 1: Server — `/api/tree` endpoint and `full=true` graph param

**Goal:** Provide the frontend with hierarchical tree data and unrestricted graph loading.

**Requirements:** R15, R16

**Dependencies:** None

**Files:**
- Modify: `src/cartograph/web/server.py`
- Modify: `tests/test_web.py`

**Approach:**
1. Add `_api_tree` handler that queries `SELECT file_path, COUNT(*) as cnt FROM nodes WHERE kind != 'file' AND file_path IS NOT NULL GROUP BY file_path`, then builds a recursive tree dict by splitting paths on `/` and summing counts up.
2. Add route `(r"^/api/tree$", self._api_tree)` to the routes list.
3. In `_api_graph`, when `params.get("full", [None])[0] == "true"`, bypass the 500-node limit (set limit to 10000 or remove).
4. Add test class `TestApiTree` with tests for tree structure, node count aggregation, and empty DB.
5. Update `TestApiGraph` to test `?full=true` param.

**Tree response shape:**
```json
{
  "tree": {
    "name": "(root)",
    "type": "directory",
    "node_count": 716,
    "children": [
      {
        "name": "src",
        "type": "directory",
        "node_count": 500,
        "children": [
          {
            "name": "cartograph",
            "type": "directory",
            "node_count": 480,
            "children": [
              { "name": "__init__.py", "type": "file", "node_count": 3, "children": [] },
              { "name": "server", "type": "directory", "node_count": 45, "children": [...] }
            ]
          }
        ]
      }
    ]
  }
}
```

**Test scenarios:**
- Happy path: tree has correct recursive structure with node counts summing up
- Edge case: single-file project (no directories)
- Edge case: deeply nested paths (5+ levels)
- `?full=true` returns more than 500 nodes

**Verification:** `GET /api/tree` returns recursive JSON. Root `node_count` matches `/api/stats` total. `GET /api/graph?full=true` returns all nodes.

---

### Unit 2: Frontend — Squarified treemap layout algorithm

**Goal:** Replace `buildGroups()` with a recursive treemap that positions nested directory/file boxes.

**Requirements:** R1, R2, R3

**Dependencies:** Unit 1 (`/api/tree` endpoint)

**Files:**
- Modify: `src/cartograph/web/frontend.py` (within FRONTEND_HTML JS)

**Approach:**

Implement squarified treemap algorithm as `buildTreemap(treeNode, x, y, w, h, depth)`:

1. Takes a tree node (from `/api/tree`) and a bounding rectangle
2. Sorts children by `node_count` descending
3. Subdivides the rectangle using squarified layout (Bruls et al.):
   - Pick the shorter axis
   - Greedily add children to a row until aspect ratio worsens
   - Lay out the row, recurse on remaining children
4. For leaf nodes (files), store the rectangle as a file group
5. For directory nodes, recurse into children with inner padding for header + margins
6. Returns a hierarchy: `{ name, type, depth, x, y, w, h, children: [...], nodes: [] }`

**Data structures:**
```js
// Tree node (matches /api/tree response)
let treeData = null;

// Computed layout (output of buildTreemap)
let layoutRoot = null;  // recursive: {name, type, depth, x, y, w, h, children, nodes}
let fileBoxes = [];     // flat list of all leaf (file) layout boxes for rendering
let dirBoxes = [];      // flat list of all directory layout boxes for rendering
```

**Constants per nesting depth:**
```js
const TREEMAP_PAD = [20, 16, 12, 10];  // outer padding at depth 0,1,2,3+
const TREEMAP_HEADER = [28, 24, 20, 18]; // header height at each depth
```

**Test scenarios:**
- Happy path: tree with 3 directories, 10 files produces non-overlapping boxes
- Edge case: single file in root (no nesting)
- Edge case: directory with one child (degenerates to full-width)
- Validation: all file boxes fit within their parent directory box

**Verification:** All boxes are non-overlapping. Every file from `/api/tree` has a corresponding box. Total area is proportional to node counts.

---

### Unit 3: Frontend — Nested box rendering on canvas

**Goal:** Render the treemap as nested rounded rectangles with headers on the canvas.

**Requirements:** R1, R4

**Dependencies:** Unit 2 (treemap layout)

**Files:**
- Modify: `src/cartograph/web/frontend.py` (within FRONTEND_HTML JS)

**Approach:**

Replace the existing `draw()` function's file-group rendering with recursive box rendering:

1. **Directory boxes:** Rendered back-to-front (deepest first for correct layering, or shallowest first since children draw over parents). Use decreasing alpha per depth: `0.15` at depth 0, `0.25` at depth 1, `0.35` at depth 2+. Fill with `--surface` color, stroke with `--border`.

2. **File boxes:** Rendered at the leaf level. Use existing `0.35` alpha fill pattern. File name as header label in `--accent` color.

3. **Header labels:** Directory names at each box's top-left. Font size decreases with depth: `14px` → `12px` → `11px` → `10px`. Color: `--text-muted` for directories, `--accent` for files.

4. **Remove HTML views:** Delete the `#overviewContainer`, `dir-grid`, `file-grid`, `dir-card`, `file-card` HTML and CSS. The canvas now renders everything.

5. **Remove navigation state machine:** Delete `viewLevel`, `currentDir`, `currentFile`, `navigateTo()`, `showDirectories()`, `showFiles()`. Replace breadcrumb with a simple "current focus" indicator.

6. **Initial camera:** `resetView()` computes bounding box of `layoutRoot` and fits it to viewport.

**Draw order (updated):**
```
1. Clear canvas, apply camera transform
2. For each dirBox (sorted by depth ascending): draw rounded rect + header
3. For each fileBox: draw rounded rect + header
4. [Unit 4: dots or nodes inside file boxes]
5. [Unit 5: cross-box bezier edges]
6. Tooltip for hovered element
```

**Test scenarios:**
- Visual: directory boxes contain their child boxes (no overflow)
- Visual: labels are readable and don't overlap box borders
- Visual: deeper boxes are visually distinguishable from shallower ones (alpha gradient)

**Verification:** Canvas renders nested boxes matching the tree structure. No overlapping boxes. Labels visible at each depth.

---

### Unit 4: Frontend — Semantic zoom (dot grid ↔ force-directed graph)

**Goal:** File boxes show compact colored dots when small on screen, expand to force-directed node graphs when large.

**Requirements:** R5, R6, R7

**Dependencies:** Unit 2 (treemap layout), Unit 3 (box rendering), Unit 1 (`/api/graph?full=true`)

**Files:**
- Modify: `src/cartograph/web/frontend.py` (within FRONTEND_HTML JS)

**Approach:**

1. **Load all nodes + edges once** on startup via `/api/graph?full=true`. Store in `graphNodes[]`, `graphEdges[]`, `nodeById{}`. Assign each node to its file box via `file_path` matching.

2. **Per-frame zoom check:** In `draw()`, for each file box, compute screen width: `boxScreenW = fileBox.w * camZoom`. If `< 200`, render dot mode. If `>= 200`, render graph mode.

3. **Dot mode rendering:**
   - Compute tight grid within file box: `cols = ceil(sqrt(n))`, spacing = `min(8, boxW / (cols+1))`
   - Draw small filled circles (radius 3px) at grid positions, colored by `nodeColor(kind)`
   - No labels, no within-file edges

4. **Graph mode rendering:**
   - Nodes rendered as labeled circles (existing pattern: `arc` + label below)
   - Within-file edges rendered as straight lines (existing pattern)
   - Each file box gets a per-file force simulation

5. **Per-file mini-simulations:**
   - Track `fileBox.sim = { running, tick, settled }` per file box
   - When a file box enters graph mode: initialize node positions in a grid within the box, start simulation
   - Simulation uses same physics (repulsion=500, attraction=0.008, damping=0.8) but with HARD boundary constraints (nodes clamped to box bounds)
   - When `settled` or exiting graph mode: freeze positions
   - Only run `requestAnimationFrame` loop when any file box has an active simulation

6. **Node position management:** Each graphNode has `dotX/dotY` (compact grid position) and `graphX/graphY` (force sim position). `draw()` reads the appropriate one based on current mode.

**Test scenarios:**
- Zoomed out: all file boxes show dot grids, no labels
- Zoomed in on one file: that file shows force graph with labels, surrounding files show dots
- Zoom transition: smoothly switches per-box as each crosses the 200px threshold
- Edge case: file with 1 node shows single dot / single labeled circle

**Verification:** At default zoom, the overview shows colored dot grids. Zooming into any area progressively reveals node labels and edges. No performance degradation (< 16ms draw time).

---

### Unit 5: Frontend — Curved bezier cross-box edges with bundling

**Goal:** Draw cross-file-box relationships as curved bezier paths, bundled when multiple edges connect the same two files.

**Requirements:** R8, R9, R10

**Dependencies:** Unit 4 (nodes positioned in file boxes)

**Files:**
- Modify: `src/cartograph/web/frontend.py` (within FRONTEND_HTML JS)

**Approach:**

1. **Edge bundling (precompute on data load):**
   - Group `graphEdges` by `{sourceFileBox, targetFileBox}` pair (using file_path)
   - For each unique pair, create a `bundledEdge = { sourceBox, targetBox, edges: [...], count }`
   - Store in `bundledEdges[]` array

2. **Bezier curve rendering:**
   - For each bundled edge, compute:
     - `start`: center of source file box edge facing target
     - `end`: center of target file box edge facing source
     - `cp1`, `cp2`: control points offset perpendicular to the straight line (offset = 30% of distance)
   - Draw with `ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, endX, endY)`
   - Line width proportional to `count` (1 + log2(count))

3. **Exit/entry point calculation:**
   - Determine which side of each box faces the other (top/right/bottom/left)
   - Place the edge endpoint at the midpoint of that side
   - Control points extend outward from the box edge, then curve toward the target

4. **Visibility:**
   - Default: draw all bundled edges at `0.12` alpha, colored by dominant edge kind
   - Hover on node: highlight its specific cross-box edges at `1.0` alpha, colored by kind
   - Hover on box header: highlight all cross-box edges from that box at `0.6` alpha

5. **Count labels:** For bundles with count > 1, draw a small label at the curve midpoint showing the count.

6. **Draw order:** Cross-box edges render AFTER all boxes but BEFORE nodes, so they appear as connections between boxes without occluding node content.

**Test scenarios:**
- Two files with one edge: single bezier curve between boxes
- Two files with 5 edges: single thick bundled curve with "5" label
- Hover on node: its specific cross-box edges highlight
- No edges between unrelated files: clean view

**Verification:** Cross-box edges are visible as smooth curves. Bundled edges show count. Hover highlights work. No edge spaghetti.

---

### Unit 6: Frontend — Interaction (hit testing, focus-zoom, hover)

**Goal:** Extend interactions for nested box layout: hierarchical hit testing, click-to-zoom-on-box, and box-level hover highlights.

**Requirements:** R11, R12, R13, R14

**Dependencies:** Units 2-5 (treemap, rendering, semantic zoom, edges)

**Files:**
- Modify: `src/cartograph/web/frontend.py` (within FRONTEND_HTML JS)

**Approach:**

1. **Hierarchical hit testing:**
   - `hitTest(sx, sy)` first checks nodes (if any file box is in graph mode), then checks file box headers, then directory box headers
   - Returns `{ type: 'node', node }` or `{ type: 'fileBox', box }` or `{ type: 'dirBox', box }` or `null`
   - Node hit testing only checks nodes in file boxes currently in graph mode (performance optimization)

2. **Click-to-zoom-on-box (R14):**
   - Clicking a file/directory box header animates the camera to fit that box in the viewport
   - Uses `camX = box.x + box.w/2`, `camY = box.y + box.h/2`, `camZoom = min(W/box.w, H/box.h) * 0.9`
   - Smooth animation over 300ms using `requestAnimationFrame` lerp

3. **Box hover highlights (R13):**
   - Hovering a box header: highlight border, show all cross-box edges from that box
   - Hovering a node: existing behavior (dim unconnected, highlight connected edges)

4. **Double-click to reset:** Double-click on empty canvas area resets view to fit all content.

5. **Preserve existing interactions:**
   - Pan (drag empty space), zoom (wheel), node click (modal), node drag

**Test scenarios:**
- Click file box header: camera animates to fit that box
- Click node in graph-mode file: opens modal
- Hover box header: cross-box edges from that box highlight
- Double-click empty: resets to overview

**Verification:** All existing interactions work. Box-level interactions (click header, hover header) work. Smooth zoom animation.

---

## System-Wide Impact

**Low impact.** Changes are contained within the web module (`frontend.py`, `server.py`). No changes to:
- Core library (parsing, indexing, storage, annotation)
- MCP server tools
- CLI interface (same `run_server(store, port)` entry point)
- Plugin manifest or skill files

**Test impact:** 3 existing test methods in `TestApiGraph` may need adjustment for `full=true` parameter. New `TestApiTree` class needed. Frontend test (`test_serves_html`) passes as long as "Cartograph" appears in the HTML.

## Risks & Dependencies

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Treemap layout performance with 700+ nodes | Low | Squarified treemap is O(n log n); computed once on load |
| Multiple active force sims causing jank | Medium | Cap at 5 active sims; settle and freeze when box leaves graph mode |
| Bezier edge computation for 100+ bundles | Low | Bundling reduces edge count; only recompute on hover |
| Large JSON payload with full=true | Low | 700 nodes + 1000 edges ≈ 200KB; fine for localhost |

## Sources & References

- Squarified Treemap Algorithm: Bruls, Huizing, van Wijk (2000)
- Requirements: `docs/brainstorms/2026-03-28-002-nested-box-graph-explorer-requirements.md`
- Research agents: architecture, patterns, flow analysis, blast radius (2026-03-28)
