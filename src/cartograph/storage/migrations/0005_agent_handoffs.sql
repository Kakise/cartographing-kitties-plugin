-- Agent handoff store: subagents persist their unified-output JSON here so the
-- orchestrator can pass `run_id`s through the conversation and reload payloads
-- only at synthesis time. Records expire automatically via `expires_at`.
--
-- Default TTL is 24h, set by callers; long-running plans may opt into 7d via
-- the DAO. The schema is additive — no drops, no renames.

CREATE TABLE IF NOT EXISTS agent_handoffs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('annotation', 'research', 'review')),
    payload TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_handoffs_session ON agent_handoffs(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_expires ON agent_handoffs(expires_at);
