-- Hybrid search (R1): dense embedding leg via sqlite-vec.
--
-- Creates a vec0 virtual table keyed by nodes.id (rowid).  Each row stores a
-- 256-d float vector for one annotated node — populated lazily by the
-- annotation pipeline (Unit 5) and an explicit back-fill.
--
-- This migration assumes the sqlite_vec extension is loaded on the connection.
-- The connection factory skips it when load fails so the lexical + centrality
-- channels keep working in degraded mode.

CREATE VIRTUAL TABLE IF NOT EXISTS nodes_vec USING vec0(
    embedding float[256]
);
