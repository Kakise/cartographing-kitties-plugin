---
title: Web Graph Explorer
type: feat
status: active
date: 2026-03-28
---

# Web Graph Explorer — Implementation Plan

## Overview

Add a `--serve` CLI option to `uvx cartographing-kittens` that starts a local web server serving an interactive graph explorer. Users can browse nodes, edges, and annotations from their browser.

## Problem Frame

After indexing and annotating a codebase, the only way to explore the graph is through MCP tool calls (which require an AI agent). A web frontend lets developers visually browse the graph database — see nodes by kind, explore edges/relationships, read annotations, and search — without needing an agent session.

## Requirements

- R1. `cartographing-kittens --serve` starts a local HTTP server on port 3333 (configurable with `--port`)
- R2. The frontend is a single self-contained HTML file served from Python (no npm, no build step)
- R3. The backend exposes a JSON REST API reading from the existing `.cartograph/graph.db`
- R4. The frontend shows: node list with filtering by kind, node detail with annotations (summary/tags/role), edges visualization, search
- R5. Zero new production dependencies — use only stdlib `http.server` or the existing `mcp` dep's underlying framework

## Scope Boundaries

**In scope:** CLI flag, HTTP server, REST API, single-file HTML/JS/CSS frontend
**Out of scope:** Graph visualization library (D3, Cytoscape), authentication, write operations, WebSocket

## Key Technical Decisions

- **stdlib `http.server`** for the web server — zero deps, simple, fits the "explore" use case
- **Single HTML file** with embedded CSS/JS — served as a string from Python, no static file management
- **Read-only API** — only GET endpoints, reuses `GraphStore` methods directly
- **Separate module** at `src/cartograph/web/` — clean separation from the MCP server

## Implementation Units

### Unit 1: CLI Entry Point + HTTP Server Skeleton

- [ ] **Goal:** `cartographing-kittens --serve` starts an HTTP server that responds on localhost
- **Files:**
  - Modify: `src/cartograph/__init__.py` (add `--serve` and `--port` arg parsing)
  - Create: `src/cartograph/web/__init__.py`
  - Create: `src/cartograph/web/server.py` (HTTP server with request routing)
  - Create: `tests/test_web.py`
- **Approach:**
  1. Add `argparse` to `main()` in `__init__.py`: `--serve` flag and `--port` (default 3333)
  2. When `--serve`: open GraphStore from `.cartograph/graph.db`, start HTTP server
  3. `server.py`: subclass `http.server.BaseHTTPRequestHandler`, route GET requests to API endpoints or serve the frontend HTML
  4. Endpoints: `GET /` (HTML frontend), `GET /api/nodes`, `GET /api/nodes/:id`, `GET /api/edges`, `GET /api/search?q=...`, `GET /api/stats`
- **Test scenarios:**
  - Happy path: Server starts and responds 200 on `/`
  - Happy path: `/api/stats` returns node/edge counts
  - Edge case: `--serve` with no `.cartograph/graph.db` shows helpful error

### Unit 2: REST API Endpoints

- [ ] **Goal:** JSON API that exposes all graph data for the frontend to consume
- **Dependencies:** Unit 1
- **Files:**
  - Modify: `src/cartograph/web/server.py`
  - Modify: `tests/test_web.py`
- **Approach:**
  API endpoints (all GET, all return JSON):
  - `GET /api/stats` — `{nodes: count, edges: count, annotated: count, pending: count}`
  - `GET /api/nodes?kind=class&limit=50&offset=0` — paginated node list with optional kind filter
  - `GET /api/nodes/:id` — single node with neighbors and edges (reuses GraphStore.get_node + get_edges)
  - `GET /api/edges?source_id=X&target_id=Y&kind=calls` — filtered edge list
  - `GET /api/search?q=term&kind=class&limit=20` — FTS search (reuses GraphStore.search)
  - `GET /api/files` — unique file paths with node counts

  All responses include annotation fields (summary, tags, role, annotation_status).
- **Test scenarios:**
  - Happy path: `/api/nodes` returns JSON array of nodes with annotation fields
  - Happy path: `/api/nodes/:id` returns node with neighbors
  - Happy path: `/api/search?q=User` returns matching nodes
  - Happy path: `/api/edges` returns edges with source/target info
  - Edge case: `/api/nodes/999999` returns 404

### Unit 3: Web Frontend

- [ ] **Goal:** Interactive single-page HTML/JS/CSS frontend for exploring the graph
- **Dependencies:** Unit 2
- **Files:**
  - Create: `src/cartograph/web/frontend.py` (contains the HTML as a Python string constant)
- **Approach:**
  Single HTML file with embedded CSS + vanilla JS (no framework, no build step):

  **Layout:**
  - Left sidebar: stats overview, kind filter chips, search bar
  - Main area: node list (table/cards), or node detail view
  - Node detail: name, kind, file:line, summary, role, tags as pills, edges grouped by direction/kind

  **Features:**
  - Filter nodes by kind (function, class, method, module, file)
  - Search via the `/api/search` endpoint
  - Click a node to see its detail + neighbors
  - Click a neighbor to navigate to it (graph browsing)
  - Annotation display: summary as text, role as badge, tags as colored pills
  - File grouping view: browse by file path

  **Style:** Dark theme matching terminal aesthetics. Minimal, fast, no external CDN deps.
- **Test scenarios:**
  - Happy path: `GET /` returns HTML with status 200
  - Happy path: Frontend makes fetch calls to `/api/*` endpoints and renders data

---

## Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| `http.server` is single-threaded | Fine for local dev exploration — not a production server |
| Large codebases may have many nodes | Pagination in API (limit/offset), virtual scroll or pagination in frontend |
| No graph.db exists yet | Check on startup, print helpful message directing user to index first |
