"""Single-file HTML frontend for the Cartograph Graph Explorer."""

FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cartograph Graph Explorer</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --yellow: #d29922; --red: #f85149; --purple: #bc8cff;
  --cyan: #39d353; --orange: #f0883e;
}
body { font: 14px/1.6 -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; background: var(--bg); color: var(--text); display: flex; height: 100vh; overflow: hidden; }

/* Sidebar */
.sidebar { width: 300px; background: var(--surface); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
.sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
.sidebar-header h1 { font-size: 16px; margin-bottom: 4px; }
.sidebar-header p { font-size: 12px; color: var(--text-muted); }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.stat { background: var(--bg); padding: 8px; border-radius: 6px; text-align: center; }
.stat-value { font-size: 20px; font-weight: 600; }
.stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; }
.search-box { padding: 12px 16px; border-bottom: 1px solid var(--border); }
.search-box input { width: 100%; padding: 8px 12px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; outline: none; }
.search-box input:focus { border-color: var(--accent); }
.kind-filters { padding: 8px 16px; border-bottom: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 4px; }
.kind-chip { padding: 3px 10px; border-radius: 12px; font-size: 11px; cursor: pointer; border: 1px solid var(--border); background: transparent; color: var(--text-muted); transition: all .15s; }
.kind-chip:hover, .kind-chip.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.file-list { flex: 1; overflow-y: auto; }
.file-group { border-bottom: 1px solid var(--border); }
.file-header { padding: 6px 16px; font-size: 12px; color: var(--accent); cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.file-header:hover { background: rgba(88,166,255,.08); }
.file-header .count { color: var(--text-muted); font-size: 11px; }
.node-item { padding: 6px 16px 6px 28px; font-size: 13px; cursor: pointer; display: flex; align-items: center; gap: 8px; }
.node-item:hover { background: rgba(88,166,255,.06); }
.node-kind { font-size: 10px; padding: 1px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
.kind-class { background: rgba(188,140,255,.2); color: var(--purple); }
.kind-function, .kind-method { background: rgba(88,166,255,.2); color: var(--accent); }
.kind-file { background: rgba(63,185,80,.2); color: var(--green); }
.kind-module { background: rgba(240,136,62,.2); color: var(--orange); }
.kind-variable, .kind-interface, .kind-type_alias, .kind-enum { background: rgba(210,153,34,.2); color: var(--yellow); }

/* Main */
.main { flex: 1; overflow: hidden; position: relative; }
.graph-container { width: 100%; height: 100%; position: relative; }
#graphCanvas { width: 100%; height: 100%; display: block; cursor: grab; }
#graphCanvas.dragging { cursor: grabbing; }
.graph-legend { position: absolute; bottom: 16px; left: 16px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 12px; font-size: 11px; pointer-events: none; opacity: .9; }
.graph-legend-item { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.graph-legend-item:last-child { margin-bottom: 0; }
.graph-legend-dot { width: 10px; height: 10px; border-radius: 50%; }
.graph-loading { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); color: var(--text-muted); font-size: 16px; }
.graph-controls { position: absolute; top: 12px; right: 12px; display: flex; gap: 4px; }
.graph-btn { background: var(--surface); border: 1px solid var(--border); color: var(--text-muted); border-radius: 6px; padding: 6px 10px; cursor: pointer; font-size: 13px; }
.graph-btn:hover { background: var(--border); color: var(--text); }

/* Search overlay */
.search-results-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg); overflow-y: auto; padding: 24px; z-index: 10; }
.search-results-overlay h3 { font-size: 16px; margin-bottom: 12px; }
.search-results-close { float: right; background: none; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.search-results-close:hover { color: var(--text); }

/* Node detail modal */
.node-detail h2 { font-size: 20px; margin-bottom: 4px; }
.node-meta { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
.node-meta a { color: var(--accent); text-decoration: none; }
.annotation-section { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 16px; margin-bottom: 16px; }
.annotation-section h3 { font-size: 13px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; }
.summary-text { font-size: 15px; line-height: 1.5; }
.role-badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; background: rgba(188,140,255,.15); color: var(--purple); border: 1px solid rgba(188,140,255,.3); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { padding: 2px 10px; border-radius: 10px; font-size: 12px; background: rgba(88,166,255,.12); color: var(--accent); border: 1px solid rgba(88,166,255,.25); }
.no-annotation { color: var(--text-muted); font-style: italic; font-size: 13px; }
.neighbors-section { margin-top: 20px; }
.neighbors-section h3 { font-size: 14px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.edge-group { margin-bottom: 16px; }
.edge-group h4 { font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }
.neighbor { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.neighbor:hover { background: rgba(88,166,255,.08); }
.edge-kind-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: var(--bg); border: 1px solid var(--border); color: var(--text-muted); }
.neighbor-summary { font-size: 12px; color: var(--text-muted); margin-left: auto; max-width: 40%; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.search-result { padding: 12px; background: var(--surface); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px; cursor: pointer; }
.search-result:hover { border-color: var(--accent); }
.search-result .name { font-weight: 600; }
.search-result .qname { font-size: 12px; color: var(--text-muted); }
.search-result .summary { font-size: 13px; margin-top: 4px; color: var(--text-muted); }

/* Node modal */
.node-modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.6); z-index: 1000; display: none; align-items: center; justify-content: center; }
.node-modal-backdrop.active { display: flex; }
.node-modal { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; max-width: 700px; width: 90%; max-height: 85vh; overflow-y: auto; padding: 24px; position: relative; }
.node-modal-close { position: absolute; top: 12px; right: 12px; background: none; border: none; color: var(--text-muted); font-size: 20px; cursor: pointer; padding: 4px 8px; border-radius: 4px; }
.node-modal-close:hover { background: var(--border); color: var(--text); }
</style>
</head>
<body>

<div class="sidebar">
  <div class="sidebar-header">
    <h1>Cartograph</h1>
    <p>Graph Explorer</p>
  </div>
  <div class="stats" id="stats"></div>
  <div class="search-box">
    <input type="text" id="searchInput" placeholder="Search nodes..." />
  </div>
  <div class="kind-filters" id="kindFilters"></div>
  <div class="file-list" id="fileList"></div>
</div>

<div class="main" id="mainContent">
  <div class="graph-container">
    <canvas id="graphCanvas"></canvas>
    <div class="graph-loading" id="graphLoading">Loading graph...</div>
    <div class="graph-legend" id="graphLegend"></div>
    <div class="graph-controls">
      <button class="graph-btn" onclick="resetView()" title="Reset zoom">Reset</button>
    </div>
  </div>
</div>

<div class="node-modal-backdrop" id="nodeModal" onclick="if(event.target===this)closeModal()">
  <div class="node-modal">
    <button class="node-modal-close" onclick="closeModal()">&times;</button>
    <div id="nodeModalContent"></div>
  </div>
</div>

<script>
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let activeKind = null;
let allNodes = [];

async function api(path) {
  const r = await fetch(path);
  if (!r.ok) { console.error('API error', r.status, await r.text()); return null; }
  return r.json();
}

function kindClass(kind) { return 'kind-' + (kind || 'unknown'); }
function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }

// ---- Kind colors for canvas ----
const KIND_COLORS = {
  'class': '#bc8cff', 'function': '#58a6ff', 'method': '#58a6ff',
  'file': '#3fb950', 'module': '#f0883e',
  'variable': '#d29922', 'interface': '#d29922', 'type_alias': '#d29922', 'enum': '#d29922'
};
const EDGE_COLORS = {
  'imports': '#8b949e', 'calls': '#58a6ff', 'inherits': '#bc8cff',
  'contains': '#3fb950', 'depends_on': '#d29922'
};
function nodeColor(kind) { return KIND_COLORS[kind] || '#8b949e'; }
function edgeColor(kind) { return EDGE_COLORS[kind] || '#30363d'; }

// ---- Graph state ----
let graphNodes = [];   // {id, x, y, vx, vy, kind, name, radius, fileBox, ...}
let graphEdges = [];   // {source, target, kind}
let nodeById = {};
let hoveredNode = null;
let hoveredBox = null;
let draggedNode = null;
let simRunning = false;
let simTick = 0;
const MAX_TICKS = 400;

// Treemap layout
let treeData = null;       // from /api/tree
let layoutRoot = null;     // recursive: {name, type, depth, x, y, w, h, children, nodes, filePath}
let fileBoxes = [];        // flat list of file layout boxes
let dirBoxes = [];         // flat list of dir layout boxes
let bundledEdges = [];     // [{sourceBox, targetBox, edges, count, dominantKind}]

// Per-file simulations
let fileSims = new Map();  // fileBox -> {running, tick, settled}

// Camera
let camX = 0, camY = 0, camZoom = 1;
let isPanning = false, panStartX = 0, panStartY = 0, panCamX = 0, panCamY = 0;
let dragStartX = 0, dragStartY = 0;

// Animation
let animating = false;
let animStart = 0, animDur = 300;
let animFromX = 0, animFromY = 0, animFromZ = 0;
let animToX = 0, animToY = 0, animToZ = 0;

const canvas = $('#graphCanvas');
const ctx = canvas.getContext('2d');

function resizeCanvas() {
  const r = canvas.parentElement.getBoundingClientRect();
  canvas.width = r.width * devicePixelRatio;
  canvas.height = r.height * devicePixelRatio;
  canvas.style.width = r.width + 'px';
  canvas.style.height = r.height + 'px';
  draw();
}

// ==== SQUARIFIED TREEMAP LAYOUT (Unit 2) ====

const TREEMAP_PAD = [20, 16, 12, 10];
const TREEMAP_HEADER = [28, 24, 20, 18];

function getPad(depth) { return TREEMAP_PAD[Math.min(depth, TREEMAP_PAD.length - 1)]; }
function getHeader(depth) { return TREEMAP_HEADER[Math.min(depth, TREEMAP_HEADER.length - 1)]; }

function squarify(children, x, y, w, h) {
  // Squarified treemap: lay out children as near-square rectangles
  if (children.length === 0) return;
  if (children.length === 1) {
    children[0]._x = x; children[0]._y = y;
    children[0]._w = w; children[0]._h = h;
    return;
  }

  const total = children.reduce((s, c) => s + (c.node_count || 1), 0);
  if (total === 0) return;

  // Sort descending by size
  const sorted = [...children].sort((a, b) => (b.node_count || 1) - (a.node_count || 1));

  let remaining = [...sorted];
  let cx = x, cy = y, cw = w, ch = h;

  while (remaining.length > 0) {
    const isWide = cw >= ch;
    const side = isWide ? ch : cw;
    const totalArea = cw * ch;
    const totalVal = remaining.reduce((s, c) => s + (c.node_count || 1), 0);

    // Greedily add items to current row until aspect ratio worsens
    let row = [remaining[0]];
    let rowVal = remaining[0].node_count || 1;

    function worstAspect(rv, items) {
      const rowArea = (rv / totalVal) * totalArea;
      const rowSide = rowArea / side;
      let worst = 0;
      for (const item of items) {
        const itemArea = ((item.node_count || 1) / totalVal) * totalArea;
        const itemSide = itemArea / rowSide;
        const aspect = Math.max(rowSide / itemSide, itemSide / rowSide);
        worst = Math.max(worst, aspect);
      }
      return worst;
    }

    for (let i = 1; i < remaining.length; i++) {
      const next = remaining[i];
      const nextVal = next.node_count || 1;
      const wa1 = worstAspect(rowVal, row);
      const wa2 = worstAspect(rowVal + nextVal, [...row, next]);
      if (wa2 <= wa1) {
        row.push(next);
        rowVal += nextVal;
      } else {
        break;
      }
    }

    // Lay out the row
    const rowFrac = rowVal / totalVal;
    const rowSize = isWide ? cw * rowFrac : ch * rowFrac;
    let pos = isWide ? cy : cx;

    for (const item of row) {
      const itemFrac = (item.node_count || 1) / rowVal;
      const itemSize = side * itemFrac;
      if (isWide) {
        item._x = cx; item._y = pos;
        item._w = rowSize; item._h = itemSize;
        pos += itemSize;
      } else {
        item._x = pos; item._y = cy;
        item._w = itemSize; item._h = rowSize;
        pos += itemSize;
      }
    }

    // Reduce remaining area
    if (isWide) {
      cx += rowSize; cw -= rowSize;
    } else {
      cy += rowSize; ch -= rowSize;
    }

    remaining = remaining.slice(row.length);
  }
}

function buildTreemap(node, x, y, w, h, depth) {
  const pad = getPad(depth);
  const header = getHeader(depth);

  const box = {
    name: node.name, type: node.type, depth,
    x, y, w, h,
    children: [], nodes: [],
    filePath: null
  };

  if (node.type === 'file') {
    box.filePath = node._filePath || node.name;
    return box;
  }

  // Inner area for children (after padding and header)
  const innerX = x + pad;
  const innerY = y + header + pad;
  const innerW = Math.max(0, w - pad * 2);
  const innerH = Math.max(0, h - header - pad * 2);

  if (innerW <= 0 || innerH <= 0 || node.children.length === 0) return box;

  // Build file paths for children
  const prefix = node._filePath || '';
  for (const c of node.children) {
    c._filePath = prefix ? prefix + '/' + c.name : c.name;
  }

  // Squarify children
  squarify(node.children, innerX, innerY, innerW, innerH);

  for (const child of node.children) {
    const childBox = buildTreemap(
      child, child._x, child._y, child._w, child._h, depth + 1
    );
    box.children.push(childBox);
  }

  return box;
}

function collectBoxes(box) {
  if (box.type === 'file') {
    fileBoxes.push(box);
  } else {
    dirBoxes.push(box);
    for (const c of box.children) collectBoxes(c);
  }
}

// ==== FORCE SIMULATION PER FILE (Unit 4) ====

const SEMANTIC_ZOOM_THRESHOLD = 200; // px on screen

function isGraphMode(box) {
  return box.w * camZoom > SEMANTIC_ZOOM_THRESHOLD;
}

function initFileNodes() {
  // Assign graphNodes to their file boxes
  const fileBoxByPath = {};
  for (const fb of fileBoxes) {
    fileBoxByPath[fb.filePath] = fb;
    fb.nodes = [];
    fb.sim = { running: false, tick: 0, settled: false };
  }

  for (const n of graphNodes) {
    const fb = fileBoxByPath[n.file_path];
    if (fb) {
      n.fileBox = fb;
      fb.nodes.push(n);
    }
  }

  // Compute dot positions and initial graph positions for each file box
  for (const fb of fileBoxes) {
    layoutNodesInBox(fb);
  }
}

function layoutNodesInBox(fb) {
  const pad = 10;
  const header = 18;
  const innerX = fb.x + pad;
  const innerY = fb.y + header + pad;
  const innerW = Math.max(1, fb.w - pad * 2);
  const innerH = Math.max(1, fb.h - header - pad * 2);

  const n = fb.nodes.length;
  if (n === 0) return;

  // Dot grid positions
  const dotCols = Math.max(1, Math.ceil(Math.sqrt(n)));
  const dotRows = Math.ceil(n / dotCols);
  const dotSpacingX = innerW / (dotCols + 1);
  const dotSpacingY = innerH / (dotRows + 1);

  for (let i = 0; i < n; i++) {
    const col = i % dotCols;
    const row = Math.floor(i / dotCols);
    fb.nodes[i].dotX = innerX + (col + 1) * dotSpacingX;
    fb.nodes[i].dotY = innerY + (row + 1) * dotSpacingY;
  }

  // Graph mode positions (initial grid, refined by force sim)
  const graphCols = Math.max(1, Math.ceil(Math.sqrt(n)));
  const graphSpacing = Math.min(60, innerW / (graphCols + 1), innerH / (Math.ceil(n / graphCols) + 1));

  for (let i = 0; i < n; i++) {
    const col = i % graphCols;
    const row = Math.floor(i / graphCols);
    fb.nodes[i].graphX = innerX + (col + 1) * graphSpacing;
    fb.nodes[i].graphY = innerY + (row + 1) * graphSpacing;
    fb.nodes[i].vx = 0;
    fb.nodes[i].vy = 0;
  }
}

function startFileSim(fb) {
  if (fb.sim.settled || fb.sim.running) return;
  fb.sim.running = true;
  fb.sim.tick = 0;
}

function tickFileSim(fb) {
  if (!fb.sim.running) return;
  fb.sim.tick++;

  const alpha = Math.max(0.001, 1 - fb.sim.tick / MAX_TICKS);
  const repulsion = 400;
  const attraction = 0.01;
  const damping = 0.8;
  const ns = fb.nodes;

  const pad = 12;
  const header = 18;
  const minX = fb.x + pad;
  const minY = fb.y + header + pad;
  const maxX = fb.x + fb.w - pad;
  const maxY = fb.y + fb.h - pad;

  // Repulsion between nodes in this file
  for (let i = 0; i < ns.length; i++) {
    for (let j = i + 1; j < ns.length; j++) {
      let dx = ns[j].graphX - ns[i].graphX;
      let dy = ns[j].graphY - ns[i].graphY;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      if (dist > 200) continue;
      const force = repulsion / (dist * dist);
      const fx = (dx / dist) * force * alpha;
      const fy = (dy / dist) * force * alpha;
      ns[i].vx -= fx; ns[i].vy -= fy;
      ns[j].vx += fx; ns[j].vy += fy;
    }
  }

  // Attraction along edges within this file
  for (const e of graphEdges) {
    if (e.source.fileBox !== fb || e.target.fileBox !== fb) continue;
    let dx = e.target.graphX - e.source.graphX;
    let dy = e.target.graphY - e.source.graphY;
    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const rest = 50;
    const force = (dist - rest) * attraction * alpha;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    e.source.vx += fx; e.source.vy += fy;
    e.target.vx -= fx; e.target.vy -= fy;
  }

  // Apply velocities with hard boundary clamping
  let energy = 0;
  for (const n of ns) {
    if (n === draggedNode) continue;
    n.vx *= damping;
    n.vy *= damping;
    n.graphX += n.vx;
    n.graphY += n.vy;
    // Hard clamp
    n.graphX = Math.max(minX + n.radius, Math.min(maxX - n.radius, n.graphX));
    n.graphY = Math.max(minY + n.radius, Math.min(maxY - n.radius, n.graphY));
    energy += n.vx * n.vx + n.vy * n.vy;
  }

  if (energy < 0.05 || fb.sim.tick >= MAX_TICKS) {
    fb.sim.running = false;
    fb.sim.settled = true;
  }
}

// ==== EDGE BUNDLING (Unit 5) ====

function computeBundledEdges() {
  bundledEdges = [];
  const pairMap = {};

  for (const e of graphEdges) {
    const sb = e.source.fileBox;
    const tb = e.target.fileBox;
    if (!sb || !tb || sb === tb) continue;
    // Canonical key
    const key = sb.filePath < tb.filePath
      ? sb.filePath + '|' + tb.filePath
      : tb.filePath + '|' + sb.filePath;
    if (!pairMap[key]) {
      pairMap[key] = { sourceBox: sb, targetBox: tb, edges: [], kinds: {} };
    }
    pairMap[key].edges.push(e);
    pairMap[key].kinds[e.kind] = (pairMap[key].kinds[e.kind] || 0) + 1;
  }

  for (const [, bundle] of Object.entries(pairMap)) {
    // Find dominant kind
    let maxKind = 'calls', maxC = 0;
    for (const [k, c] of Object.entries(bundle.kinds)) {
      if (c > maxC) { maxC = c; maxKind = k; }
    }
    bundledEdges.push({
      sourceBox: bundle.sourceBox,
      targetBox: bundle.targetBox,
      edges: bundle.edges,
      count: bundle.edges.length,
      dominantKind: maxKind
    });
  }
}

function boxCenter(box) {
  return { x: box.x + box.w / 2, y: box.y + box.h / 2 };
}

function boxEdgePoint(box, targetX, targetY) {
  // Find the point on box border closest to the direction of (targetX, targetY)
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  const dx = targetX - cx;
  const dy = targetY - cy;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return { x: cx, y: cy };

  const scaleX = dx !== 0 ? (box.w / 2) / Math.abs(dx) : Infinity;
  const scaleY = dy !== 0 ? (box.h / 2) / Math.abs(dy) : Infinity;
  const scale = Math.min(scaleX, scaleY);
  return { x: cx + dx * scale, y: cy + dy * scale };
}

// ==== RENDERING (Unit 3) ====

function roundRect(x, y, w, h, r) {
  if (w < 0 || h < 0) return;
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

// Depth-based alpha for boxes
function boxAlpha(depth) {
  const alphas = [0.12, 0.18, 0.25, 0.3];
  return alphas[Math.min(depth, alphas.length - 1)];
}

function draw() {
  const W = canvas.width;
  const H = canvas.height;
  const dpr = devicePixelRatio;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);

  if (!layoutRoot) return;

  // Apply camera transform
  ctx.setTransform(dpr * camZoom, 0, 0, dpr * camZoom,
    -camX * dpr * camZoom + W / 2,
    -camY * dpr * camZoom + H / 2);

  // 1. Draw directory boxes (sorted by depth ascending = outermost first)
  const sortedDirs = [...dirBoxes].sort((a, b) => a.depth - b.depth);
  for (const db of sortedDirs) {
    if (db.w < 2 || db.h < 2) continue;
    ctx.globalAlpha = boxAlpha(db.depth);
    roundRect(db.x, db.y, db.w, db.h, Math.max(4, 12 - db.depth * 2));
    ctx.fillStyle = '#161b22';
    ctx.fill();
    ctx.strokeStyle = db === hoveredBox ? '#58a6ff' : '#30363d';
    ctx.lineWidth = (db === hoveredBox ? 2 : 1) / camZoom;
    ctx.stroke();

    // Directory label
    const headerH = getHeader(db.depth);
    const fontSize = Math.max(8, Math.min(14 - db.depth, headerH - 8));
    if (db.w * camZoom > 50) {
      ctx.globalAlpha = 0.7;
      ctx.font = `600 ${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = '#8b949e';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      const maxLabelW = db.w - 10;
      let label = db.name;
      while (ctx.measureText(label).width > maxLabelW && label.length > 3) {
        label = label.slice(0, -2) + '..';
      }
      ctx.fillText(label, db.x + 6, db.y + 4);
    }
  }

  // 2. Draw file boxes
  for (const fb of fileBoxes) {
    if (fb.w < 2 || fb.h < 2) continue;
    ctx.globalAlpha = 0.35;
    roundRect(fb.x, fb.y, fb.w, fb.h, 6);
    ctx.fillStyle = '#0d1117';
    ctx.fill();
    ctx.strokeStyle = fb === hoveredBox ? '#58a6ff' : '#30363d';
    ctx.lineWidth = (fb === hoveredBox ? 2 : 0.5) / camZoom;
    ctx.stroke();

    // File label
    if (fb.w * camZoom > 40) {
      ctx.globalAlpha = 0.7;
      const fontSize = Math.max(7, Math.min(11, fb.w * camZoom / 20));
      ctx.font = `600 ${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = '#58a6ff';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      let label = fb.name;
      const maxLabelW = fb.w - 6;
      while (ctx.measureText(label).width > maxLabelW && label.length > 3) {
        label = label.slice(0, -2) + '..';
      }
      ctx.fillText(label, fb.x + 4, fb.y + 2);
    }

    // 3. Draw nodes inside file box (semantic zoom)
    if (fb.nodes.length === 0) continue;

    if (isGraphMode(fb)) {
      // Start simulation if not settled
      startFileSim(fb);
      drawGraphModeNodes(fb);
    } else {
      drawDotModeNodes(fb);
    }
  }

  ctx.globalAlpha = 1;

  // 4. Draw bundled cross-box edges
  drawBundledEdges();

  // 5. Tooltip
  if (hoveredNode && camZoom > 0.2) {
    const n = hoveredNode;
    const nx = isGraphMode(n.fileBox) ? n.graphX : n.dotX;
    const ny = isGraphMode(n.fileBox) ? n.graphY : n.dotY;
    const fontSize = Math.max(10, 12 / camZoom);
    ctx.font = `${fontSize}px -apple-system, sans-serif`;
    const text = n.qualified_name || n.name;
    const tw = ctx.measureText(text).width;
    const pad = 5 / camZoom;
    ctx.globalAlpha = 1;
    ctx.fillStyle = 'rgba(22,27,34,.95)';
    roundRect(nx - tw / 2 - pad, ny - n.radius - fontSize - pad * 3, tw + pad * 2, fontSize + pad * 2, 4);
    ctx.fill();
    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 0.5 / camZoom;
    ctx.stroke();
    ctx.fillStyle = '#e6edf3';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(text, nx, ny - n.radius - fontSize - pad * 2);
  }

  ctx.globalAlpha = 1;
}

function drawDotModeNodes(fb) {
  const ns = fb.nodes;
  for (const n of ns) {
    const isHovered = n === hoveredNode;
    const dimmed = hoveredNode && !isHovered && n.fileBox !== hoveredNode.fileBox;
    ctx.globalAlpha = dimmed ? 0.1 : 0.8;
    ctx.beginPath();
    ctx.arc(n.dotX, n.dotY, Math.min(3, fb.w / (Math.sqrt(ns.length) * 3)), 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n.kind);
    ctx.fill();
  }
}

function drawGraphModeNodes(fb) {
  const ns = fb.nodes;

  // Draw within-file edges first
  ctx.lineWidth = 1 / camZoom;
  for (const e of graphEdges) {
    if (e.source.fileBox !== fb || e.target.fileBox !== fb) continue;
    const isHighlighted = hoveredNode && (e.source === hoveredNode || e.target === hoveredNode);
    ctx.globalAlpha = isHighlighted ? 0.8 : 0.2;
    ctx.strokeStyle = isHighlighted ? edgeColor(e.kind) : 'rgba(48,54,61,.5)';
    if (isHighlighted) ctx.lineWidth = 2 / camZoom;
    ctx.beginPath();
    ctx.moveTo(e.source.graphX, e.source.graphY);
    ctx.lineTo(e.target.graphX, e.target.graphY);
    ctx.stroke();
    ctx.lineWidth = 1 / camZoom;
  }

  // Draw nodes
  for (const n of ns) {
    const isHovered = n === hoveredNode;
    const isConnected = hoveredNode && graphEdges.some(e =>
      (e.source === hoveredNode && e.target === n) || (e.target === hoveredNode && e.source === n));
    const dimmed = hoveredNode && !isHovered && !isConnected;

    ctx.globalAlpha = dimmed ? 0.15 : 1;
    ctx.beginPath();
    ctx.arc(n.graphX, n.graphY, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n.kind);
    ctx.fill();

    if (isHovered) {
      ctx.strokeStyle = '#e6edf3';
      ctx.lineWidth = 2 / camZoom;
      ctx.stroke();
    }

    // Labels (only when zoomed enough)
    if (fb.w * camZoom > 300 || isHovered) {
      const fontSize = Math.max(8, 10 / camZoom);
      ctx.font = `${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = dimmed ? 'rgba(139,148,158,.2)' : '#e6edf3';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const label = n.name.length > 18 ? n.name.slice(0, 16) + '..' : n.name;
      ctx.fillText(label, n.graphX, n.graphY + n.radius + 2);
    }
  }
}

function drawBundledEdges() {
  if (bundledEdges.length === 0) return;

  for (const be of bundledEdges) {
    const sc = boxCenter(be.sourceBox);
    const tc = boxCenter(be.targetBox);
    const sp = boxEdgePoint(be.sourceBox, tc.x, tc.y);
    const ep = boxEdgePoint(be.targetBox, sc.x, sc.y);

    // Compute control points for bezier curve
    const mx = (sp.x + ep.x) / 2;
    const my = (sp.y + ep.y) / 2;
    const dx = ep.x - sp.x;
    const dy = ep.y - sp.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const perpX = -dy / (dist || 1) * dist * 0.2;
    const perpY = dx / (dist || 1) * dist * 0.2;
    const cp1x = mx + perpX * 0.5;
    const cp1y = my + perpY * 0.5;
    const cp2x = mx - perpX * 0.5;
    const cp2y = my - perpY * 0.5;

    // Check if this edge should be highlighted
    const hoverHighlight = hoveredNode && be.edges.some(e =>
      e.source === hoveredNode || e.target === hoveredNode);
    const boxHighlight = hoveredBox && (be.sourceBox === hoveredBox || be.targetBox === hoveredBox);
    const highlighted = hoverHighlight || boxHighlight;

    ctx.globalAlpha = highlighted ? 0.7 : 0.12;
    ctx.strokeStyle = edgeColor(be.dominantKind);
    ctx.lineWidth = (1 + Math.log2(Math.max(1, be.count))) / camZoom;
    if (highlighted) ctx.lineWidth *= 1.5;

    ctx.beginPath();
    ctx.moveTo(sp.x, sp.y);
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, ep.x, ep.y);
    ctx.stroke();

    // Count label for bundles > 1
    if (be.count > 1 && (highlighted || camZoom > 0.4)) {
      const labelX = (sp.x + 2 * cp1x + 2 * cp2x + ep.x) / 6;
      const labelY = (sp.y + 2 * cp1y + 2 * cp2y + ep.y) / 6;
      const fontSize = Math.max(8, 10 / camZoom);
      ctx.font = `600 ${fontSize}px -apple-system, sans-serif`;
      ctx.globalAlpha = highlighted ? 0.9 : 0.4;
      ctx.fillStyle = edgeColor(be.dominantKind);
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(String(be.count), labelX, labelY);
    }
  }

  ctx.globalAlpha = 1;
}

// ==== HIT TESTING & INTERACTION (Unit 6) ====

function screenToWorld(sx, sy) {
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  return {
    x: (sx - W / 2) / camZoom + camX,
    y: (sy - H / 2) / camZoom + camY
  };
}

function hitTest(sx, sy) {
  const { x, y } = screenToWorld(sx, sy);

  // Check nodes in graph-mode file boxes first
  for (const fb of fileBoxes) {
    if (!isGraphMode(fb)) continue;
    for (let i = fb.nodes.length - 1; i >= 0; i--) {
      const n = fb.nodes[i];
      const dx = x - n.graphX, dy = y - n.graphY;
      if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) {
        return { type: 'node', node: n };
      }
    }
  }

  // Check nodes in dot-mode file boxes (with larger hit area)
  for (const fb of fileBoxes) {
    if (isGraphMode(fb)) continue;
    for (let i = fb.nodes.length - 1; i >= 0; i--) {
      const n = fb.nodes[i];
      const dx = x - n.dotX, dy = y - n.dotY;
      if (dx * dx + dy * dy <= 36) { // 6px hit radius for dots
        return { type: 'node', node: n };
      }
    }
  }

  // Check file box headers
  for (const fb of fileBoxes) {
    if (x >= fb.x && x <= fb.x + fb.w && y >= fb.y && y <= fb.y + 18) {
      return { type: 'fileBox', box: fb };
    }
  }

  // Check dir box headers (deepest first)
  const sortedDirsDeep = [...dirBoxes].sort((a, b) => b.depth - a.depth);
  for (const db of sortedDirsDeep) {
    const headerH = getHeader(db.depth);
    if (x >= db.x && x <= db.x + db.w && y >= db.y && y <= db.y + headerH) {
      return { type: 'dirBox', box: db };
    }
  }

  return null;
}

// ---- Canvas events ----
canvas.addEventListener('mousedown', (e) => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const hit = hitTest(sx, sy);
  if (hit && hit.type === 'node' && isGraphMode(hit.node.fileBox)) {
    draggedNode = hit.node;
    dragStartX = e.clientX; dragStartY = e.clientY;
    canvas.classList.add('dragging');
  } else {
    isPanning = true;
    panStartX = e.clientX; panStartY = e.clientY;
    panCamX = camX; panCamY = camY;
    canvas.classList.add('dragging');
  }
});

canvas.addEventListener('mousemove', (e) => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  if (draggedNode) {
    const { x, y } = screenToWorld(sx, sy);
    draggedNode.graphX = x; draggedNode.graphY = y;
    draggedNode.vx = 0; draggedNode.vy = 0;
    draw();
  } else if (isPanning) {
    camX = panCamX - (e.clientX - panStartX) / camZoom;
    camY = panCamY - (e.clientY - panStartY) / camZoom;
    draw();
  } else {
    const prevNode = hoveredNode;
    const prevBox = hoveredBox;
    hoveredNode = null;
    hoveredBox = null;
    const hit = hitTest(sx, sy);
    if (hit) {
      if (hit.type === 'node') hoveredNode = hit.node;
      else hoveredBox = hit.box;
    }
    canvas.style.cursor = hoveredNode ? 'pointer' : (hoveredBox ? 'pointer' : 'grab');
    if (prevNode !== hoveredNode || prevBox !== hoveredBox) draw();
  }
});

canvas.addEventListener('mouseup', (e) => {
  if (draggedNode) {
    const dist = Math.abs(e.clientX - dragStartX) + Math.abs(e.clientY - dragStartY);
    if (dist < 5) {
      showNodeModal(draggedNode.id);
    } else {
      // Restart sim for this file box
      const fb = draggedNode.fileBox;
      if (fb) { fb.sim.settled = false; fb.sim.running = false; startFileSim(fb); }
    }
    draggedNode = null;
    canvas.classList.remove('dragging');
  }
  if (isPanning) {
    isPanning = false;
    canvas.classList.remove('dragging');
  }
});

canvas.addEventListener('click', (e) => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const hit = hitTest(sx, sy);
  if (hit && hit.type === 'node' && !isGraphMode(hit.node.fileBox)) {
    // Click on dot-mode node opens modal
    showNodeModal(hit.node.id);
  } else if (hit && (hit.type === 'fileBox' || hit.type === 'dirBox')) {
    // Click on box header zooms to fit that box
    animateToBox(hit.box);
  }
});

canvas.addEventListener('dblclick', (e) => {
  e.preventDefault();
  resetView();
});

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const { x: wx, y: wy } = screenToWorld(sx, sy);
  const factor = e.deltaY < 0 ? 1.12 : 0.89;
  camZoom = Math.max(0.05, Math.min(10, camZoom * factor));
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  camX = wx - (sx - W / 2) / camZoom;
  camY = wy - (sy - H / 2) / camZoom;
  draw();
}, { passive: false });

// ---- Camera animation ----
function animateToBox(box) {
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  animFromX = camX; animFromY = camY; animFromZ = camZoom;
  animToX = box.x + box.w / 2;
  animToY = box.y + box.h / 2;
  animToZ = Math.min(3, Math.min(W / (box.w + 40), H / (box.h + 40)));
  animStart = performance.now();
  animDur = 300;
  animating = true;
  requestAnimationFrame(animateStep);
}

function animateStep(now) {
  if (!animating) return;
  const t = Math.min(1, (now - animStart) / animDur);
  const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; // ease in-out
  camX = animFromX + (animToX - animFromX) * ease;
  camY = animFromY + (animToY - animFromY) * ease;
  camZoom = animFromZ + (animToZ - animFromZ) * ease;
  draw();
  if (t < 1) requestAnimationFrame(animateStep);
  else animating = false;
}

function resetView() {
  if (!layoutRoot) return;
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  animFromX = camX; animFromY = camY; animFromZ = camZoom;
  animToX = layoutRoot.x + layoutRoot.w / 2;
  animToY = layoutRoot.y + layoutRoot.h / 2;
  animToZ = Math.min(1.5, Math.min(W / (layoutRoot.w + 60), H / (layoutRoot.h + 60)));
  animStart = performance.now();
  animDur = 300;
  animating = true;
  requestAnimationFrame(animateStep);
}

// ==== SIMULATION LOOP ====

function simLoop() {
  let anyRunning = false;
  for (const fb of fileBoxes) {
    if (isGraphMode(fb) && fb.sim.running) {
      tickFileSim(fb);
      anyRunning = true;
    }
  }
  if (anyRunning) {
    draw();
    requestAnimationFrame(simLoop);
  }
}

function checkSimulations() {
  let needsLoop = false;
  for (const fb of fileBoxes) {
    if (isGraphMode(fb) && !fb.sim.settled) {
      startFileSim(fb);
      needsLoop = true;
    }
  }
  if (needsLoop) requestAnimationFrame(simLoop);
}

// ==== DATA LOADING ====

async function loadTreeAndGraph() {
  const [treeResp, graphResp] = await Promise.all([
    api('/api/tree'),
    api('/api/graph?full=true')
  ]);

  if (!treeResp || !graphResp) {
    $('#graphLoading').textContent = 'Failed to load data';
    return;
  }

  treeData = treeResp.tree;

  // Build treemap layout
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  const layoutW = Math.max(1200, W * 2);
  const layoutH = Math.max(900, H * 2);

  fileBoxes = [];
  dirBoxes = [];
  layoutRoot = buildTreemap(treeData, 0, 0, layoutW, layoutH, 0);
  collectBoxes(layoutRoot);

  // Process graph data
  nodeById = {};
  const edgeCounts = {};
  for (const e of graphResp.edges) {
    edgeCounts[e.source_id] = (edgeCounts[e.source_id] || 0) + 1;
    edgeCounts[e.target_id] = (edgeCounts[e.target_id] || 0) + 1;
  }

  graphNodes = graphResp.nodes.filter(n => n.kind !== 'file').map(n => {
    const edgeCount = edgeCounts[n.id] || 0;
    const gn = {
      id: n.id, kind: n.kind, name: n.name,
      qualified_name: n.qualified_name,
      file_path: n.file_path || '(unknown)',
      dotX: 0, dotY: 0,
      graphX: 0, graphY: 0,
      vx: 0, vy: 0,
      radius: Math.max(4, Math.min(12, 4 + edgeCount)),
      fileBox: null
    };
    nodeById[n.id] = gn;
    return gn;
  });

  graphEdges = graphResp.edges
    .filter(e => nodeById[e.source_id] && nodeById[e.target_id])
    .map(e => ({ source: nodeById[e.source_id], target: nodeById[e.target_id], kind: e.kind }));

  // Assign nodes to file boxes and compute positions
  initFileNodes();

  // Bundle cross-box edges
  computeBundledEdges();

  // Build legend
  const usedKinds = [...new Set(graphNodes.map(n => n.kind))].sort();
  $('#graphLegend').innerHTML = usedKinds.map(k =>
    `<div class="graph-legend-item"><div class="graph-legend-dot" style="background:${nodeColor(k)}"></div>${k}</div>`
  ).join('');

  $('#graphLoading').style.display = 'none';

  // Center camera
  camX = layoutRoot.x + layoutRoot.w / 2;
  camY = layoutRoot.y + layoutRoot.h / 2;
  const spanX = layoutRoot.w + 60;
  const spanY = layoutRoot.h + 60;
  camZoom = Math.min(1.5, Math.min(
    (canvas.width / devicePixelRatio) / spanX,
    (canvas.height / devicePixelRatio) / spanY
  ));

  draw();
  checkSimulations();
}

// ---- Sidebar ----
async function loadStats() {
  const s = await api('/api/stats');
  if (!s) return;
  $('#stats').innerHTML = `
    <div class="stat"><div class="stat-value">${s.nodes}</div><div class="stat-label">Nodes</div></div>
    <div class="stat"><div class="stat-value">${s.edges}</div><div class="stat-label">Edges</div></div>
    <div class="stat"><div class="stat-value">${s.annotated}</div><div class="stat-label">Annotated</div></div>
    <div class="stat"><div class="stat-value">${s.pending}</div><div class="stat-label">Pending</div></div>
  `;
  const kinds = Object.entries(s.kinds).sort((a,b) => b[1]-a[1]);
  $('#kindFilters').innerHTML = `<button class="kind-chip active" data-kind="">All</button>` +
    kinds.map(([k,c]) => `<button class="kind-chip" data-kind="${k}">${k} (${c})</button>`).join('');

  $$('.kind-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      $$('.kind-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeKind = chip.dataset.kind || null;
      loadFiles();
    });
  });
}

async function loadFiles() {
  const suffix = activeKind ? `?kind=${activeKind}&limit=500` : '?limit=500';
  const data = await api('/api/nodes' + suffix);
  if (!data) return;
  allNodes = data.nodes;

  const byFile = {};
  for (const n of allNodes) {
    const fp = n.file_path || '(unknown)';
    if (!byFile[fp]) byFile[fp] = [];
    byFile[fp].push(n);
  }

  const html = Object.entries(byFile).sort((a,b) => a[0].localeCompare(b[0])).map(([fp, nodes]) => `
    <div class="file-group">
      <div class="file-header" onclick="this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? '' : 'none'">
        <span>${fp}</span>
        <span class="count">${nodes.length}</span>
      </div>
      <div>
        ${nodes.filter(n => n.kind !== 'file').map(n => `
          <div class="node-item" onclick="showNodeModal(${n.id})">
            <span class="node-kind ${kindClass(n.kind)}">${n.kind}</span>
            <span>${n.name}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
  $('#fileList').innerHTML = html;
}

// ---- Modal ----
async function showNodeModal(id) {
  const data = await api(`/api/nodes/${id}`);
  if (!data) return;
  const n = data.node;
  const neighbors = data.neighbors;

  const annoStatus = n.annotation_status === 'annotated';
  const summaryHtml = annoStatus && n.summary
    ? `<div class="summary-text">${esc(n.summary)}</div>`
    : '<div class="no-annotation">Not annotated</div>';
  const roleHtml = annoStatus && n.role
    ? `<span class="role-badge">${esc(n.role)}</span>` : '';
  const tagsHtml = annoStatus && n.tags && n.tags.length
    ? `<div class="tags">${n.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>` : '';

  const outgoing = neighbors.filter(e => e.direction === 'outgoing');
  const incoming = neighbors.filter(e => e.direction === 'incoming');

  function neighborHtml(list) {
    const byKind = {};
    for (const e of list) {
      if (!byKind[e.edge_kind]) byKind[e.edge_kind] = [];
      byKind[e.edge_kind].push(e);
    }
    return Object.entries(byKind).map(([kind, edges]) => `
      <div class="edge-group">
        <h4>${kind} (${edges.length})</h4>
        ${edges.map(e => `
          <div class="neighbor" onclick="showNodeModal(${e.node.id})">
            <span class="node-kind ${kindClass(e.node.kind)}">${e.node.kind}</span>
            <span>${esc(e.node.name)}</span>
            <span class="edge-kind-badge">${kind}</span>
            ${e.node.summary ? `<span class="neighbor-summary">${esc(e.node.summary)}</span>` : ''}
          </div>
        `).join('')}
      </div>
    `).join('');
  }

  const loc = n.start_line ? `${n.file_path}:${n.start_line}-${n.end_line}` : n.file_path;

  $('#nodeModalContent').innerHTML = `
    <div class="node-detail">
      <h2><span class="node-kind ${kindClass(n.kind)}">${n.kind}</span> ${esc(n.name)}</h2>
      <div class="node-meta">
        <code>${esc(n.qualified_name)}</code><br>
        <span>${esc(loc)}</span>
      </div>
      <div class="annotation-section">
        <h3>Summary</h3>
        ${summaryHtml}
      </div>
      ${roleHtml || tagsHtml ? `
      <div class="annotation-section">
        <h3>Role & Tags</h3>
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap;">
          ${roleHtml}
          ${tagsHtml}
        </div>
      </div>
      ` : ''}
      ${outgoing.length ? `
      <div class="neighbors-section">
        <h3>Outgoing (${outgoing.length})</h3>
        ${neighborHtml(outgoing)}
      </div>` : ''}
      ${incoming.length ? `
      <div class="neighbors-section">
        <h3>Incoming (${incoming.length})</h3>
        ${neighborHtml(incoming)}
      </div>` : ''}
    </div>
  `;
  $('#nodeModal').classList.add('active');
}

function closeModal() {
  $('#nodeModal').classList.remove('active');
}

// ---- Search ----
async function doSearch(query) {
  const existing = document.querySelector('.search-results-overlay');
  if (existing) existing.remove();
  if (!query.trim()) return;
  const data = await api(`/api/search?q=${encodeURIComponent(query)}&limit=30`);
  if (!data || !data.results.length) return;

  const overlay = document.createElement('div');
  overlay.className = 'search-results-overlay';
  overlay.innerHTML = `
    <button class="search-results-close" onclick="this.parentElement.remove()">&times;</button>
    <h3>${data.count} results for "${esc(query)}"</h3>
    ${data.results.map(r => `
      <div class="search-result" onclick="showNodeModal(${r.id}); this.closest('.search-results-overlay').remove();">
        <span class="node-kind ${kindClass(r.kind)}">${r.kind}</span>
        <span class="name">${esc(r.name)}</span>
        <div class="qname">${esc(r.qualified_name)}</div>
        ${r.summary ? `<div class="summary">${esc(r.summary)}</div>` : ''}
      </div>
    `).join('')}
  `;
  $('#mainContent').appendChild(overlay);
}

// ---- Init ----
let searchTimer;
$('#searchInput').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => doSearch(e.target.value), 300);
});

// Re-check simulations on zoom change (semantic zoom mode switch)
let lastZoom = 0;
function onZoomChange() {
  if (Math.abs(camZoom - lastZoom) > 0.01) {
    lastZoom = camZoom;
    checkSimulations();
  }
}
canvas.addEventListener('wheel', () => setTimeout(onZoomChange, 50));

window.addEventListener('resize', resizeCanvas);
resizeCanvas();
loadStats();
loadFiles();
loadTreeAndGraph();
</script>
</body>
</html>
"""
