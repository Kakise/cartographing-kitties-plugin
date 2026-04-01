# Nested Box Graph Explorer — Requirements

## Problem Frame

The web graph explorer needs a single-canvas view where the codebase structure is immediately visible as **nested boxes** — directories contain sub-directory/file boxes recursively, files contain node graphs. A developer should be able to see the entire codebase architecture at a glance, zoom into any area for detail, and understand cross-module relationships through visible edges.

The current 3-level drill-down hides relationships between modules (you can only see one file at a time). The original flat view was closer to the right idea but failed because all 700+ nodes were rendered at the same scale with no grouping hierarchy.

## Codebase Context

**Key files:**
- `src/cartograph/web/frontend.py` — Single-file HTML/CSS/JS frontend (~1000 lines), embedded as Python string `FRONTEND_HTML`
- `src/cartograph/web/server.py` — HTTP server with REST API endpoints including `/api/graph`, `/api/directories`, `/api/nodes/:id`

**Existing patterns to preserve:**
- Single-file frontend architecture (no build tools, no external JS deps)
- Center-anchored camera model (`camX/camY/camZoom` with zoom-toward-cursor)
- Immediate-mode canvas rendering (`draw()` rebuilds each frame)
- HiDPI-aware canvas sizing
- Dark theme color system (`KIND_COLORS`, `EDGE_COLORS`, CSS custom properties)
- Node modal for detail view (click node → fetch `/api/nodes/:id` → show modal)
- Sidebar with stats, search, kind filters, file list

**Existing API endpoints available:**
- `GET /api/graph?limit=N` — all nodes + edges (capped at 500)
- `GET /api/graph?directory=X` — nodes in a directory
- `GET /api/graph?file_path=X` — nodes in a file
- `GET /api/directories` — directory-level aggregation (path, node_count, file_count, kinds)
- `GET /api/search?q=X` — FTS5 search
- `GET /api/nodes/:id` — node detail with neighbors

## Requirements

### Layout

- R1. **Recursive nested boxes on a single canvas.** The entire codebase is rendered as nested rounded rectangles: root → top-level directories → sub-directories → files → nodes. Each level is visually contained within its parent box.

- R2. **Squarified treemap layout.** Boxes at each level are arranged using a squarified treemap algorithm (Bruls et al.), sized by node count. This produces a compact, space-efficient, roughly square arrangement rather than a vertical column.

- R3. **Dynamic box sizing.** Box dimensions are proportional to the total number of symbols they contain (recursively). A directory with 100 symbols gets ~10x the area of one with 10 symbols.

- R4. **Header labels.** Each box has a header showing its name (directory name or filename). Headers use decreasing font sizes at deeper nesting levels.

### Semantic Zoom (Hybrid Rendering)

- R5. **Compact dot grid at overview zoom.** When zoomed out (file box on screen < 200px), nodes inside file boxes are rendered as small colored dots in a tight grid. Dots are color-coded by kind. No labels, no internal edges.

- R6. **Force-directed graph when zoomed in.** When zoomed into a file box (box on screen > 200px), nodes expand into labeled circles with a force simulation. Internal edges between nodes within the same file are drawn. Labels appear below each node.

- R7. **Smooth transition.** The switch between dot and graph mode should happen per-file-box independently based on its screen-space size, creating a natural semantic zoom as the user navigates.

### Cross-Box Edges

- R8. **Curved bezier edges between boxes.** When a node in one box has a relationship to a node in another box, draw a curved bezier path between them. The curve should route naturally (exit from the edge of the source box, arc, enter the target box).

- R9. **Cross-box edges visible by default** at low opacity (~0.15 alpha). When hovering a node, its cross-box edges highlight to full opacity and are colored by edge kind.

- R10. **Edge bundling for density.** When multiple edges connect the same two file boxes, bundle them visually as a single thicker line with a count label rather than drawing N separate curves. This prevents edge spaghetti.

### Interaction

- R11. **Pan and zoom** — preserve existing camera model. Mouse drag to pan, scroll wheel to zoom toward cursor.

- R12. **Click node → modal** — preserve existing node modal behavior (fetch detail from `/api/nodes/:id`, show summary, tags, role, neighbors).

- R13. **Hover highlights** — hovering a node dims unconnected nodes and highlights connected edges (both within-file and cross-file). Hovering a box border highlights all cross-box edges from that box.

- R14. **Click box header to focus** — clicking a directory/file header zooms the camera to fit that box in the viewport.

### API

- R15. **New `/api/tree` endpoint.** Returns the full directory tree structure with node counts at each level, enabling the recursive treemap layout without multiple API calls:
  ```json
  {
    "name": "src/cartograph",
    "type": "directory",
    "node_count": 150,
    "children": [
      { "name": "server", "type": "directory", "node_count": 45, "children": [...] },
      { "name": "__init__.py", "type": "file", "node_count": 3, "children": [] }
    ]
  }
  ```

- R16. **Load all nodes + edges.** The graph endpoint should return ALL nodes and edges (no 500 limit) since the semantic zoom means only a fraction are rendered in detail at any time. Add a new `/api/graph?full=true` parameter that bypasses the limit.

## Success Criteria

- A developer can open the explorer and immediately see the directory structure as nested boxes in a treemap layout
- Zooming into any area progressively reveals more detail (dot grid → labeled graph)
- Cross-module relationships are visible as curved bezier edges between boxes
- No overlapping labels or boxes at any zoom level
- The view is usable with 700+ nodes without performance issues
- All existing functionality preserved: search, kind filters, node modal, sidebar

## Scope Boundaries

**In scope:**
- Recursive treemap layout algorithm
- Semantic zoom (dot mode / graph mode per file box)
- Curved bezier cross-box edges with bundling
- Click-to-zoom-to-box navigation
- New `/api/tree` endpoint
- Removing the 500-node API limit (with `full=true` param)

**Out of scope:**
- Collapsible/expandable boxes (rely on semantic zoom instead)
- Edge routing that avoids crossing boxes (simple bezier curves are sufficient)
- Minimap or overview-in-corner widget
- Saving/loading view state or bookmarks
- 3D rendering or WebGL

## Key Decisions

- **Treemap over force-directed for box layout**: Force layouts are non-deterministic and cause overlapping at scale. Treemaps guarantee no overlap and produce compact, squarish boxes. The force simulation is only used *inside* file boxes when zoomed in.
- **Semantic zoom over drill-down**: Single canvas with all levels visible simultaneously preserves spatial context. The user can always see where they are relative to the whole codebase.
- **Edge bundling for cross-box edges**: With 1000+ edges, drawing every individual cross-box edge would create visual noise. Bundling edges between the same two file boxes keeps the overview readable.
- **Bezier curves over straight lines**: Straight lines through nested boxes are visually confusing. Bezier curves that exit/enter at box edges feel more natural and are easier to follow.

## Open Questions

### Resolve Before Planning
- None — requirements are well-scoped.

### Deferred
- Should deeply nested directories (4+ levels) be collapsed to reduce nesting depth?
- Should there be a level-of-detail slider to manually control the semantic zoom threshold?
