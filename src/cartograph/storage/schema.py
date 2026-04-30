"""SQLite schema definitions for the Cartograph graph store.

This module retains the full schema definition for reference and documentation.
Actual schema creation and evolution is handled by the migration system in
``cartograph.storage.migrations``.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK(kind IN ('function', 'class', 'method', 'interface', 'type_alias', 'enum', 'module', 'file')),
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    language TEXT,
    summary TEXT,
    annotation_status TEXT DEFAULT 'pending' CHECK(annotation_status IN ('pending', 'annotated', 'failed')),
    content_hash TEXT,
    properties TEXT,
    annotated_content_hash TEXT,
    graph_version INTEGER DEFAULT 0,
    centrality REAL,
    in_degree_cache INTEGER,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK(kind IN ('imports', 'calls', 'inherits', 'contains', 'depends_on')),
    weight REAL DEFAULT 1.0,
    properties TEXT,
    updated_at TEXT,
    UNIQUE(source_id, target_id, kind)
);

CREATE TABLE IF NOT EXISTS graph_meta (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    graph_version INTEGER NOT NULL DEFAULT 0,
    centrality_version INTEGER NOT NULL DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    name,
    qualified_name,
    summary,
    content='nodes',
    content_rowid='id',
    tokenize='porter'
);

-- FTS sync triggers
CREATE TRIGGER IF NOT EXISTS nodes_fts_insert AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, name, qualified_name, summary)
    VALUES (new.id, new.name, new.qualified_name, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_update AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, name, qualified_name, summary)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.summary);
    INSERT INTO nodes_fts(rowid, name, qualified_name, summary)
    VALUES (new.id, new.name, new.qualified_name, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS nodes_fts_delete AFTER DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, name, qualified_name, summary)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.summary);
END;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nodes_file_path ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_kind ON nodes(kind);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_qualified_name ON nodes(qualified_name);
CREATE INDEX IF NOT EXISTS idx_nodes_annotation_status ON nodes(annotation_status);
CREATE INDEX IF NOT EXISTS idx_nodes_graph_version ON nodes(graph_version);
CREATE INDEX IF NOT EXISTS idx_nodes_centrality ON nodes(centrality DESC);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind);
CREATE INDEX IF NOT EXISTS idx_edges_updated_at ON edges(updated_at);

CREATE TABLE IF NOT EXISTS litter_box (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('failure','anti-pattern','unsupported','regression','never-do')),
    description TEXT NOT NULL,
    context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    source_agent TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS treat_box (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('best-practice','validated-pattern','always-do','convention','optimization')),
    description TEXT NOT NULL,
    context TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    source_agent TEXT DEFAULT ''
);
"""
