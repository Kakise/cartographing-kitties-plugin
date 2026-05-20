# Subgraph Context Format

Standard structured text format produced by skill orchestrators and consumed by agents.
Orchestrators build this by calling Cartographing Kittensing Kittens MCP tools before dispatching agents.

## Why This Exists

Plugin subagents cannot call MCP tools directly (platform limitation). Skill orchestrators
run in the main conversation with MCP access, so they pre-compute graph context and pass
it as structured text to agents. This format standardizes that contract.

## Format Specification

### Section 1: Annotation Status

```
## Annotation Status
- Annotated: 120 nodes
- Pending: 45 nodes
- Failed: 2 nodes
- Coverage: 71%

> Note: Low annotation coverage may limit the quality of summaries and roles below.
```

Include this so agents know whether to trust summaries/roles or fall back to source reading.

### Section 2: Memory Context

```
## Memory Context

### Litter lessons to avoid
- `[anti-pattern]` Circular imports between service modules
  Context: src/services/user.py, src/services/order.py

### Treat lessons to follow
- `[convention]` Route handlers delegate validation to service-layer validators
  Context: src/api/routes.py

### Memory gaps
- No relevant entries found for "payments"
```

Include this before changed/target nodes for planning, work, and review orchestrators.
Populate it by following `memory-workflow.md`.

### Section 3: Changed/Target Nodes

```
## Changed Nodes

### `services.user::UserService` (class)
- **File:** src/services/user_service.py:15-89
- **Summary:** Handles user CRUD operations with validation and caching
- **Role:** Business logic layer
- **Tags:** service, database, validation
- **Status:** annotated

### `services.user::UserService::create_user` (method)
- **File:** src/services/user_service.py:22-45
- **Summary:** Creates a new user with input validation
- **Role:** Input handler
- **Tags:** validation, database
- **Status:** annotated
```

One subsection per changed/target node. Include all annotation fields.
For unannotated nodes, show `Status: pending` and omit Summary/Role/Tags.

### Section 4: Edges Between Changed Nodes

```
## Edges Between Changed Nodes

- `UserService::create_user` --calls--> `User::__init__` (both changed — verify contract)
- `UserService::create_user` --calls--> `validate_email` (both changed — verify contract)
- `main::app` --imports--> `UserService` (both changed — verify import still valid)
```

This section highlights relationships where BOTH endpoints changed — the highest-risk
contracts to verify. Edge kinds: `imports`, `calls`, `inherits`, `contains`, `depends_on`.

### Section 5: Neighbors (1-hop)

```
## Neighbors

### Callers of changed nodes (incoming edges)
- `tests.test_user::TestUser::test_create` --calls--> `UserService::create_user`
  Summary: Tests user creation with valid and invalid inputs | Role: Test case

### Callees of changed nodes (outgoing edges)
- `UserService::create_user` --calls--> `db.session::commit`
  Summary: Commits pending database transaction | Role: Data access layer
```

Include summaries and roles when available. Group by edge direction.

### Section 6: Transitive Dependents (blast radius)

```
## Transitive Dependents (blast radius)

### Depth 1 (direct)
- `main::app` (module) — Role: Application entry point — Tags: api, routing
- `tests.test_user::TestUser` (class) — Role: Test case — Tags: testing

### Depth 2
- `api.routes::user_router` (function) — Role: API handler — Tags: api, routing

### Summary by role
- 2 API handlers, 1 test class, 1 entry point affected
```

Group by depth. Include role-based summary at the end for quick assessment.

### Section 7: Transitive Dependencies (upstream)

```
## Transitive Dependencies (upstream)

### Depth 1 (direct)
- `models.user::User` (class) — Role: Data model — Tags: models, database
- `utils.validators::validate_email` (function) — Role: Input validator — Tags: validation

### Depth 2
- `db.connection::get_session` (function) — Role: Data access layer — Tags: database
```

Same structure as dependents but for upstream dependencies.

## Orchestrator-Specific Variations

### Review orchestrator
Includes all 7 sections. Section 3 is "Changed Nodes" (from diff).
Calls: `annotation_status`, `get_file_structure` per modified file, `query_node` per modified symbol,
`find_dependents` for public symbols, `find_dependencies` for all modified symbols.
Also calls `query_litter_box` and `query_treat_box` for memory preflight.

### Plan/Brainstorm orchestrator
Sections 1, 2, 3, 5, 6, 7. Section 3 is "Target Nodes" (from search results in the feature area).
Calls: `annotation_status`, `search` with feature keywords, `get_file_structure` on key files,
`query_node` on important symbols, `find_dependencies`/`find_dependents` for the target area.
Also calls `query_litter_box` and `query_treat_box` for memory preflight.

### Work orchestrator
Sections 1, 2, 3, 5. Section 3 is "Target Nodes" (from implementation unit's file list).
Calls: `get_file_structure` per target file, `query_node` on key symbols.
Also calls `query_litter_box` and `query_treat_box` before implementation and
`add_litter_box_entry`/`add_treat_box_entry` after validated lessons.

### Annotate orchestrator
Does not use this format. Passes raw `get_pending_annotations` batch data instead.

## Agent Expectations

Every agent's "Expected Context" section declares which sections it needs:

| Agent Type | Sections Used |
|-----------|---------------|
| Correctness reviewer | 1, 2, 3, 4, 5 |
| Testing reviewer | 1, 2, 3, 5, 6 |
| Impact reviewer | 1, 2, 3, 4, 6 |
| Structure reviewer | 1, 2, 3, 5, 7 |
| Researcher | 1, 2, 3, 5 |
| Pattern analyst | 1, 2, 3, 5 |
| Flow analyzer | 1, 2, 3, 5, 7 |
| Impact analyst | 1, 2, 3, 6 |
| Workers | 1, 2, 3, 5 |

Agents should fall back to `Read`/`Grep` when graph context is insufficient.
