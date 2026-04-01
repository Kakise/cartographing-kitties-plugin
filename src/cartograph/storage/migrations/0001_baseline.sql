-- Baseline migration: captures the original schema.
-- For fresh databases this creates all tables.  For existing databases
-- the migration runner stamps version=1 without executing this file
-- (all statements use IF NOT EXISTS so it is safe either way).

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
    UNIQUE(source_id, target_id, kind)
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
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_kind ON edges(kind);

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
