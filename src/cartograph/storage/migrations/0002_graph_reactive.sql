-- Graph-reactive engineering schema additions.

-- Global metadata table (single-row counter for graph versioning).
CREATE TABLE IF NOT EXISTS graph_meta (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    graph_version INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO graph_meta (id, graph_version) VALUES (1, 0);

-- Stale annotation detection: records the content_hash at annotation time.
ALTER TABLE nodes ADD COLUMN annotated_content_hash TEXT;

-- Version stamping: which indexing run last touched this node.
ALTER TABLE nodes ADD COLUMN graph_version INTEGER DEFAULT 0;

-- Edge timestamps for diff detection.
ALTER TABLE edges ADD COLUMN updated_at TEXT;

-- Backfill: set annotated_content_hash for already-annotated nodes.
UPDATE nodes SET annotated_content_hash = content_hash
WHERE annotation_status = 'annotated';

-- Indexes for new columns.
CREATE INDEX IF NOT EXISTS idx_nodes_graph_version ON nodes(graph_version);
CREATE INDEX IF NOT EXISTS idx_edges_updated_at ON edges(updated_at);
