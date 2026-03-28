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
.main { flex: 1; overflow-y: auto; padding: 24px; }
.welcome { text-align: center; padding: 80px 20px; color: var(--text-muted); }
.welcome h2 { font-size: 24px; margin-bottom: 8px; color: var(--text); }

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
  <div class="welcome">
    <h2>Cartograph Graph Explorer</h2>
    <p>Browse your codebase graph. Click a node to explore its annotations and relationships.</p>
  </div>
</div>

<script>
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let activeKind = null;
let allNodes = [];

async function api(path) {
  const r = await fetch(path);
  return r.json();
}

function kindClass(kind) {
  return 'kind-' + (kind || 'unknown');
}

async function loadStats() {
  const s = await api('/api/stats');
  $('#stats').innerHTML = `
    <div class="stat"><div class="stat-value">${s.nodes}</div><div class="stat-label">Nodes</div></div>
    <div class="stat"><div class="stat-value">${s.edges}</div><div class="stat-label">Edges</div></div>
    <div class="stat"><div class="stat-value">${s.annotated}</div><div class="stat-label">Annotated</div></div>
    <div class="stat"><div class="stat-value">${s.pending}</div><div class="stat-label">Pending</div></div>
  `;
  // Kind filters
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

  // Group by file
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
          <div class="node-item" onclick="loadNode(${n.id})">
            <span class="node-kind ${kindClass(n.kind)}">${n.kind}</span>
            <span>${n.name}</span>
          </div>
        `).join('')}
      </div>
    </div>
  `).join('');
  $('#fileList').innerHTML = html;
}

async function loadNode(id) {
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

  // Group neighbors
  const outgoing = neighbors.filter(e => e.direction === 'outgoing');
  const incoming = neighbors.filter(e => e.direction === 'incoming');

  function neighborHtml(list) {
    // Group by edge_kind
    const byKind = {};
    for (const e of list) {
      if (!byKind[e.edge_kind]) byKind[e.edge_kind] = [];
      byKind[e.edge_kind].push(e);
    }
    return Object.entries(byKind).map(([kind, edges]) => `
      <div class="edge-group">
        <h4>${kind} (${edges.length})</h4>
        ${edges.map(e => `
          <div class="neighbor" onclick="loadNode(${e.node.id})">
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

  $('#mainContent').innerHTML = `
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
}

async function doSearch(query) {
  if (!query.trim()) { loadFiles(); return; }
  const data = await api(`/api/search?q=${encodeURIComponent(query)}&limit=30`);

  if (!data.results.length) {
    $('#mainContent').innerHTML = `<div class="welcome"><p>No results for "${esc(query)}"</p></div>`;
    return;
  }

  $('#mainContent').innerHTML = `
    <div class="search-results">
      <h3>${data.count} results for "${esc(query)}"</h3>
      ${data.results.map(r => `
        <div class="search-result" onclick="loadNode(${r.id})">
          <span class="node-kind ${kindClass(r.kind)}">${r.kind}</span>
          <span class="name">${esc(r.name)}</span>
          <div class="qname">${esc(r.qualified_name)}</div>
          ${r.summary ? `<div class="summary">${esc(r.summary)}</div>` : ''}
        </div>
      `).join('')}
    </div>
  `;
}

function esc(s) { return s ? String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : ''; }

// Init
let searchTimer;
$('#searchInput').addEventListener('input', (e) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => doSearch(e.target.value), 300);
});

loadStats();
loadFiles();
</script>
</body>
</html>
"""
