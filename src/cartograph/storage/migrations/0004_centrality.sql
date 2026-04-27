-- Centrality surface (R6): cache PageRank-style centrality and in-degree on nodes.

-- Per-node centrality score, normalised to [0, 1].  NULL until first compute.
ALTER TABLE nodes ADD COLUMN centrality REAL;

-- Cached direct in-degree (number of incoming edges).  Mirrors a GROUP BY over
-- edges.target_id for join-friendly queries.  NULL until first compute.
ALTER TABLE nodes ADD COLUMN in_degree_cache INTEGER;

-- Sentinel versioning column: centrality is stale when this lags graph_version.
ALTER TABLE graph_meta ADD COLUMN centrality_version INTEGER NOT NULL DEFAULT 0;

-- Index used by rank_by_centrality and context-summary top-K pruning.
CREATE INDEX IF NOT EXISTS idx_nodes_centrality ON nodes(centrality DESC);
