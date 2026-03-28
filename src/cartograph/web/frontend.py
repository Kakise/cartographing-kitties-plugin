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
.main { flex: 1; overflow: hidden; position: relative; padding: 0; }
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
.search-results-overlay { position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: var(--bg); overflow-y: auto; padding: 24px; z-index: 10; }
.search-results-overlay h3 { font-size: 16px; margin-bottom: 12px; }
.search-results-close { float: right; background: none; border: none; color: var(--text-muted); font-size: 18px; cursor: pointer; }
.search-results-close:hover { color: var(--text); }

/* Node detail */
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

/* Neighbors */
.neighbors-section { margin-top: 20px; }
.neighbors-section h3 { font-size: 14px; margin-bottom: 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
.edge-group { margin-bottom: 16px; }
.edge-group h4 { font-size: 12px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 6px; }
.neighbor { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.neighbor:hover { background: rgba(88,166,255,.08); }
.edge-kind-badge { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: var(--bg); border: 1px solid var(--border); color: var(--text-muted); }
.neighbor-summary { font-size: 12px; color: var(--text-muted); margin-left: auto; max-width: 40%; text-align: right; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* Search results */
.search-results h3 { font-size: 16px; margin-bottom: 12px; }
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
let graphNodes = [];  // {id, x, y, vx, vy, kind, name, radius, component}
let graphEdges = [];  // {source, target, kind} (references to graphNodes entries)
let nodeById = {};
let hoveredNode = null;
let draggedNode = null;
let simRunning = false;
let simTick = 0;
const MAX_TICKS = 600;

// Camera
let camX = 0, camY = 0, camZoom = 1;
let isPanning = false, panStartX = 0, panStartY = 0, panCamX = 0, panCamY = 0;
let dragStartX = 0, dragStartY = 0;

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

// ---- Hierarchical grouping: directory -> file ----
let fileGroups = [];  // [{dir, file, nodes, x, y, w, h}]
let dirGroups = [];   // [{dir, files: [fileGroup], x, y, w, h}]

function buildGroups() {
  // Group nodes by file_path, then by directory
  const byFile = {};
  for (const n of graphNodes) {
    const fp = n.file_path || '(unknown)';
    if (!byFile[fp]) byFile[fp] = [];
    byFile[fp].push(n);
  }

  const byDir = {};
  for (const [fp, nodes] of Object.entries(byFile)) {
    const parts = fp.split('/');
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : '(root)';
    const file = parts[parts.length - 1];
    if (!byDir[dir]) byDir[dir] = [];
    byDir[dir].push({ dir, file, fullPath: fp, nodes });
  }

  // Layout: arrange directories top-to-bottom, files left-to-right within each dir
  const PAD = 20;
  const NODE_SPACING = 50;
  const FILE_PAD = 30;
  const DIR_PAD = 20;
  const DIR_GAP = 40;
  const FILE_GAP = 30;
  const HEADER_H = 24;

  fileGroups = [];
  dirGroups = [];

  let cursorY = DIR_PAD;

  const sortedDirs = Object.entries(byDir).sort((a, b) => a[0].localeCompare(b[0]));

  for (const [dir, files] of sortedDirs) {
    files.sort((a, b) => a.file.localeCompare(b.file));

    let fileX = DIR_PAD;
    let maxFileH = 0;
    const dirFiles = [];

    for (const fg of files) {
      // Layout nodes in a grid within this file group
      const cols = Math.max(1, Math.ceil(Math.sqrt(fg.nodes.length)));
      const rows = Math.ceil(fg.nodes.length / cols);
      const fw = cols * NODE_SPACING + FILE_PAD * 2;
      const fh = rows * NODE_SPACING + FILE_PAD * 2 + HEADER_H;

      const fileGroup = {
        dir, file: fg.file, fullPath: fg.fullPath,
        nodes: fg.nodes,
        x: fileX, y: cursorY + HEADER_H + DIR_PAD,
        w: fw, h: fh
      };

      // Position nodes within the file box
      for (let i = 0; i < fg.nodes.length; i++) {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const n = fg.nodes[i];
        n.x = fileGroup.x + FILE_PAD + col * NODE_SPACING + NODE_SPACING / 2;
        n.y = fileGroup.y + FILE_PAD + HEADER_H + row * NODE_SPACING + NODE_SPACING / 2;
        n.vx = 0;
        n.vy = 0;
        n.fileGroup = fileGroup;
      }

      dirFiles.push(fileGroup);
      fileGroups.push(fileGroup);
      fileX += fw + FILE_GAP;
      maxFileH = Math.max(maxFileH, fh);
    }

    const dirW = fileX - FILE_GAP + DIR_PAD;
    const dirH = maxFileH + HEADER_H + DIR_PAD * 2;

    dirGroups.push({
      dir,
      files: dirFiles,
      x: 0, y: cursorY,
      w: dirW, h: dirH
    });

    cursorY += dirH + DIR_GAP;
  }

  // Center horizontally
  const maxW = Math.max(...dirGroups.map(d => d.w));
  for (const dg of dirGroups) {
    const shift = (maxW - dg.w) / 2;
    dg.x += shift;
    for (const fg of dg.files) {
      fg.x += shift;
      for (const n of fg.nodes) n.x += shift;
    }
  }
}

// ---- Force simulation (within-file repulsion + edge attraction) ----
function initSimulation() {
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;

  buildGroups();

  // Center camera
  if (graphNodes.length > 0) {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const dg of dirGroups) {
      minX = Math.min(minX, dg.x);
      maxX = Math.max(maxX, dg.x + dg.w);
      minY = Math.min(minY, dg.y);
      maxY = Math.max(maxY, dg.y + dg.h);
    }
    camX = (minX + maxX) / 2;
    camY = (minY + maxY) / 2;
    const spanX = maxX - minX + 100;
    const spanY = maxY - minY + 100;
    camZoom = Math.min(1.5, Math.min(W / spanX, H / spanY));
  }

  simTick = 0;
  simRunning = true;
  requestAnimationFrame(simulate);
}

function simulate() {
  if (!simRunning) return;
  simTick++;

  const alpha = Math.max(0.001, 1 - simTick / MAX_TICKS);
  const repulsion = 400;
  const attraction = 0.01;
  const damping = 0.8;

  // Repulsion between nodes in the same file group
  for (const fg of fileGroups) {
    const ns = fg.nodes;
    for (let i = 0; i < ns.length; i++) {
      for (let j = i + 1; j < ns.length; j++) {
        let dx = ns[j].x - ns[i].x;
        let dy = ns[j].y - ns[i].y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        if (dist > 200) continue;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force * alpha;
        const fy = (dy / dist) * force * alpha;
        ns[i].vx -= fx; ns[i].vy -= fy;
        ns[j].vx += fx; ns[j].vy += fy;
      }
    }
  }

  // Attraction along edges (weaker for cross-file)
  for (const e of graphEdges) {
    const s = e.source;
    const t = e.target;
    let dx = t.x - s.x;
    let dy = t.y - s.y;
    let dist = Math.sqrt(dx * dx + dy * dy) || 1;
    const sameFile = s.fileGroup === t.fileGroup;
    const str = sameFile ? attraction : attraction * 0.2;
    const rest = sameFile ? 50 : 150;
    const force = (dist - rest) * str * alpha;
    const fx = (dx / dist) * force;
    const fy = (dy / dist) * force;
    s.vx += fx; s.vy += fy;
    t.vx -= fx; t.vy -= fy;
  }

  // Apply velocities + constrain to file group bounds
  let energy = 0;
  for (const n of graphNodes) {
    if (n === draggedNode) continue;
    n.vx *= damping;
    n.vy *= damping;
    n.x += n.vx;
    n.y += n.vy;

    // Soft constraint: pull back toward file group
    if (n.fileGroup) {
      const fg = n.fileGroup;
      const margin = 15;
      const cx = fg.x + fg.w / 2;
      const cy = fg.y + fg.h / 2;
      if (n.x < fg.x + margin) n.vx += 0.5;
      if (n.x > fg.x + fg.w - margin) n.vx -= 0.5;
      if (n.y < fg.y + 24 + margin) n.vy += 0.5;
      if (n.y > fg.y + fg.h - margin) n.vy -= 0.5;
    }

    energy += n.vx * n.vx + n.vy * n.vy;
  }

  // Update group bounds based on actual node positions
  for (const fg of fileGroups) {
    if (fg.nodes.length === 0) continue;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of fg.nodes) {
      minX = Math.min(minX, n.x - n.radius);
      maxX = Math.max(maxX, n.x + n.radius);
      minY = Math.min(minY, n.y - n.radius);
      maxY = Math.max(maxY, n.y + n.radius);
    }
    const pad = 25;
    fg.x = minX - pad;
    fg.y = minY - pad - 24;
    fg.w = maxX - minX + pad * 2;
    fg.h = maxY - minY + pad * 2 + 24;
  }
  for (const dg of dirGroups) {
    if (dg.files.length === 0) continue;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const fg of dg.files) {
      minX = Math.min(minX, fg.x);
      maxX = Math.max(maxX, fg.x + fg.w);
      minY = Math.min(minY, fg.y);
      maxY = Math.max(maxY, fg.y + fg.h);
    }
    const pad = 15;
    dg.x = minX - pad;
    dg.y = minY - pad - 24;
    dg.w = maxX - minX + pad * 2;
    dg.h = maxY - minY + pad * 2 + 24;
  }

  draw();

  if (energy < 0.1 || simTick >= MAX_TICKS) {
    simRunning = false;
  } else {
    requestAnimationFrame(simulate);
  }
}

// ---- Rendering ----
function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function draw() {
  const W = canvas.width;
  const H = canvas.height;
  const dpr = devicePixelRatio;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, W, H);

  // Apply camera transform
  ctx.setTransform(dpr * camZoom, 0, 0, dpr * camZoom, -camX * dpr * camZoom + W / 2, -camY * dpr * camZoom + H / 2);

  // Draw directory groups (background)
  for (const dg of dirGroups) {
    ctx.globalAlpha = 0.3;
    roundRect(dg.x, dg.y, dg.w, dg.h, 12);
    ctx.fillStyle = '#161b22';
    ctx.fill();
    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 1 / camZoom;
    ctx.stroke();

    // Directory label
    ctx.globalAlpha = 0.7;
    const dirFontSize = Math.max(10, 13 / camZoom);
    ctx.font = `600 ${dirFontSize}px -apple-system, sans-serif`;
    ctx.fillStyle = '#8b949e';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(dg.dir, dg.x + 10, dg.y + 6);
  }

  // Draw file groups
  for (const fg of fileGroups) {
    ctx.globalAlpha = 0.25;
    roundRect(fg.x, fg.y, fg.w, fg.h, 8);
    ctx.fillStyle = '#0d1117';
    ctx.fill();
    ctx.strokeStyle = '#30363d';
    ctx.lineWidth = 0.5 / camZoom;
    ctx.stroke();

    // File label
    ctx.globalAlpha = 0.6;
    const fileFontSize = Math.max(8, 11 / camZoom);
    ctx.font = `${fileFontSize}px -apple-system, sans-serif`;
    ctx.fillStyle = '#58a6ff';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(fg.file, fg.x + 8, fg.y + 5);
  }

  ctx.globalAlpha = 1;

  // Draw edges
  ctx.lineWidth = 1 / camZoom;
  for (const e of graphEdges) {
    const s = e.source;
    const t = e.target;
    const isHighlighted = hoveredNode && (s === hoveredNode || t === hoveredNode);
    const crossFile = s.fileGroup !== t.fileGroup;
    if (!isHighlighted && !crossFile) {
      ctx.strokeStyle = 'rgba(48,54,61,.4)';
      ctx.globalAlpha = 0.3;
    } else if (isHighlighted) {
      ctx.strokeStyle = edgeColor(e.kind);
      ctx.globalAlpha = 1;
    } else {
      // Cross-file edges: more visible
      ctx.strokeStyle = edgeColor(e.kind);
      ctx.globalAlpha = 0.35;
    }
    ctx.beginPath();
    ctx.moveTo(s.x, s.y);
    ctx.lineTo(t.x, t.y);
    ctx.stroke();
  }

  ctx.globalAlpha = 1;

  // Draw nodes
  for (const n of graphNodes) {
    const isHovered = n === hoveredNode;
    const isConnected = hoveredNode && graphEdges.some(e => (e.source === hoveredNode && e.target === n) || (e.target === hoveredNode && e.source === n));
    const dimmed = hoveredNode && !isHovered && !isConnected;

    ctx.globalAlpha = dimmed ? 0.2 : 1;
    ctx.beginPath();
    ctx.arc(n.x, n.y, n.radius, 0, Math.PI * 2);
    ctx.fillStyle = nodeColor(n.kind);
    ctx.fill();

    if (isHovered) {
      ctx.strokeStyle = '#e6edf3';
      ctx.lineWidth = 2 / camZoom;
      ctx.stroke();
    }

    // Labels
    if (camZoom > 0.4 || isHovered) {
      const fontSize = Math.max(8, 10 / camZoom);
      ctx.font = `${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = dimmed ? 'rgba(139,148,158,.3)' : '#e6edf3';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const label = n.name.length > 18 ? n.name.slice(0, 16) + '..' : n.name;
      ctx.fillText(label, n.x, n.y + n.radius + 2);
    }
  }

  ctx.globalAlpha = 1;

  // Tooltip for hovered node
  if (hoveredNode && camZoom > 0.3) {
    const n = hoveredNode;
    const fontSize = Math.max(10, 12 / camZoom);
    ctx.font = `${fontSize}px -apple-system, sans-serif`;
    const text = n.qualified_name || n.name;
    const tw = ctx.measureText(text).width;
    const pad = 4 / camZoom;
    ctx.fillStyle = 'rgba(22,27,34,.95)';
    roundRect(n.x - tw / 2 - pad, n.y - n.radius - fontSize - pad * 3, tw + pad * 2, fontSize + pad * 2, 4);
    ctx.fill();
    ctx.fillStyle = '#e6edf3';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(text, n.x, n.y - n.radius - fontSize - pad * 2);
  }
}

// ---- Hit testing ----
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
  for (let i = graphNodes.length - 1; i >= 0; i--) {
    const n = graphNodes[i];
    const dx = x - n.x, dy = y - n.y;
    if (dx * dx + dy * dy <= (n.radius + 4) * (n.radius + 4)) return n;
  }
  return null;
}

// ---- Canvas events ----
canvas.addEventListener('mousedown', (e) => {
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const node = hitTest(sx, sy);
  if (node) {
    draggedNode = node;
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
    draggedNode.x = x; draggedNode.y = y;
    draggedNode.vx = 0; draggedNode.vy = 0;
    draw();
  } else if (isPanning) {
    camX = panCamX - (e.clientX - panStartX) / camZoom;
    camY = panCamY - (e.clientY - panStartY) / camZoom;
    draw();
  } else {
    const prev = hoveredNode;
    hoveredNode = hitTest(sx, sy);
    canvas.style.cursor = hoveredNode ? 'pointer' : 'grab';
    if (prev !== hoveredNode) draw();
  }
});

canvas.addEventListener('mouseup', (e) => {
  if (draggedNode) {
    const rect = canvas.getBoundingClientRect();
    const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
    const node = hitTest(sx, sy);
    // If it was a click (not drag), open modal
    const dist = Math.abs(e.clientX - dragStartX) + Math.abs(e.clientY - dragStartY);
    if (dist < 5) {
      showNodeModal(draggedNode.id);
    }
    draggedNode = null;
    canvas.classList.remove('dragging');
    if (!simRunning) { simRunning = true; simTick = Math.max(simTick, MAX_TICKS - 100); requestAnimationFrame(simulate); }
  }
  if (isPanning) {
    isPanning = false;
    canvas.classList.remove('dragging');
  }
});

canvas.addEventListener('wheel', (e) => {
  e.preventDefault();
  const rect = canvas.getBoundingClientRect();
  const sx = e.clientX - rect.left, sy = e.clientY - rect.top;
  const { x: wx, y: wy } = screenToWorld(sx, sy);
  const factor = e.deltaY < 0 ? 1.1 : 0.9;
  camZoom = Math.max(0.1, Math.min(5, camZoom * factor));
  // Adjust camera so the point under the cursor stays fixed
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  camX = wx - (sx - W / 2) / camZoom;
  camY = wy - (sy - H / 2) / camZoom;
  draw();
}, { passive: false });

function resetView() {
  if (dirGroups.length === 0 && graphNodes.length === 0) return;
  const W = canvas.width / devicePixelRatio;
  const H = canvas.height / devicePixelRatio;
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const dg of dirGroups) {
    minX = Math.min(minX, dg.x);
    maxX = Math.max(maxX, dg.x + dg.w);
    minY = Math.min(minY, dg.y);
    maxY = Math.max(maxY, dg.y + dg.h);
  }
  camX = (minX + maxX) / 2;
  camY = (minY + maxY) / 2;
  const spanX = maxX - minX + 100;
  const spanY = maxY - minY + 100;
  camZoom = Math.min(1.5, Math.min(W / spanX, H / spanY));
  draw();
}

// ---- Load graph data ----
async function loadGraph() {
  const data = await api('/api/graph?limit=500');
  if (!data) { $('#graphLoading').textContent = 'Failed to load graph'; return; }
  nodeById = {};

  // Pre-compute edge counts in O(E)
  const edgeCounts = {};
  for (const e of data.edges) {
    edgeCounts[e.source_id] = (edgeCounts[e.source_id] || 0) + 1;
    edgeCounts[e.target_id] = (edgeCounts[e.target_id] || 0) + 1;
  }

  graphNodes = data.nodes.filter(n => n.kind !== 'file').map(n => {
    const edgeCount = edgeCounts[n.id] || 0;
    const gn = {
      id: n.id, kind: n.kind, name: n.name,
      qualified_name: n.qualified_name,
      file_path: n.file_path || '(unknown)',
      x: 0, y: 0, vx: 0, vy: 0,
      radius: Math.max(4, Math.min(14, 4 + edgeCount * 1.5)),
      fileGroup: null
    };
    nodeById[n.id] = gn;
    return gn;
  });

  graphEdges = data.edges
    .filter(e => nodeById[e.source_id] && nodeById[e.target_id])
    .map(e => ({ source: nodeById[e.source_id], target: nodeById[e.target_id], kind: e.kind, source_id: e.source_id, target_id: e.target_id }));

  $('#graphLoading').style.display = 'none';

  // Build legend
  const usedKinds = [...new Set(graphNodes.map(n => n.kind))].sort();
  $('#graphLegend').innerHTML = usedKinds.map(k =>
    `<div class="graph-legend-item"><div class="graph-legend-dot" style="background:${nodeColor(k)}"></div>${k}</div>`
  ).join('');

  if (graphNodes.length > 0) {
    initSimulation();
  }
}

// ---- Sidebar ----
async function loadStats() {
  const s = await api('/api/stats');
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
async function loadNode(id) { showNodeModal(id); }

async function showNodeModal(id) {
  const data = await api(`/api/nodes/${id}`);
  const n = data.node;
  const neighbors = data.neighbors;

  const annoStatus = n.annotation_status === 'annotated';
  const summaryHtml = annoStatus && n.summary
    ? `<div class="summary-text">${esc(n.summary)}</div>`
    : '<div class="no-annotation">Not annotated</div>';
  const roleHtml = annoStatus && n.role
    ? `<span class="role-badge">${esc(n.role)}</span>`
    : '';
  const tagsHtml = annoStatus && n.tags && n.tags.length
    ? `<div class="tags">${n.tags.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>`
    : '';

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

// ---- Search (overlay on top of graph) ----
async function doSearch(query) {
  // Remove any existing search overlay
  const existing = document.querySelector('.search-results-overlay');
  if (existing) existing.remove();

  if (!query.trim()) return;
  const data = await api(`/api/search?q=${encodeURIComponent(query)}&limit=30`);

  if (!data.results.length) return;

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

window.addEventListener('resize', resizeCanvas);
resizeCanvas();
loadStats();
loadFiles();
loadGraph();
</script>
</body>
</html>
"""
