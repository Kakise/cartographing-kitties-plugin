# Tool Reference

Detailed parameters, return values, and examples for all 15 Cartographing Kittens MCP tools.

## Table of Contents

1. [index_codebase](#index_codebase)
2. [query_node](#query_node)
3. [find_dependencies](#find_dependencies)
4. [find_dependents](#find_dependents)
5. [search](#search)
6. [get_file_structure](#get_file_structure)
7. [annotation_status](#annotation_status)
8. [get_pending_annotations](#get_pending_annotations)
9. [submit_annotations](#submit_annotations)
10. [graph_diff](#graph_diff)
11. [validate_graph](#validate_graph)
12. [batch_query_nodes](#batch_query_nodes)
13. [get_context_summary](#get_context_summary)
14. [find_stale_annotations](#find_stale_annotations)
15. [rank_nodes](#rank_nodes)

---

## index_codebase

Trigger structural indexing. Parses source files with tree-sitter, extracts definitions
and relationships, and stores them in the graph.

**Parameters:**
- `full` (bool, default `false`) — `true` re-indexes everything, `false` only processes changed files.

**Returns:**
```json
{
  "files_parsed": 42,
  "nodes_created": 380,
  "edges_created": 520,
  "files_deleted": 2,
  "errors": [],
  "diff_available": true,
  "diff_summary": "12 nodes added, 3 removed, 8 modified, 15 edges added, 5 edges removed"
}
```

`diff_available` is `true` when the run detected changes (incremental mode). Call
`graph_diff()` immediately after to get the full structural diff.

**When to use:** At conversation start, or after significant code changes.

**Examples:**
```
"Index this codebase so I can explore its structure"
→ index_codebase(full=false)

"Something feels off, do a full reindex"
→ index_codebase(full=true)
```

---

## query_node

Look up a specific function, class, or module by name. Returns the node with its
immediate neighbors — what it imports, calls, inherits from, and what calls/imports it.

**Parameters:**
- `name` (str, required) — Name or qualified name to look up. Tries exact qualified name first,
  then falls back to partial name match.

**Returns:**
```json
{
  "found": true,
  "node": {
    "id": 42, "kind": "class", "name": "UserService",
    "qualified_name": "services.user::UserService",
    "file_path": "services/user.py", "start_line": 15, "end_line": 89,
    "language": "python", "summary": "Handles user CRUD with caching",
    "annotation_status": "annotated",
    "tags": ["service", "database", "validation"],
    "role": "Business logic layer"
  },
  "neighbors": [
    { "direction": "outgoing", "edge_kind": "imports", "node": { "...same fields..." } },
    { "direction": "incoming", "edge_kind": "calls", "node": { "...same fields..." } }
  ]
}
```

**Examples:**
```
"Tell me about the UserService class"
→ query_node(name="UserService")

"What does models.user::User::display_name do?"
→ query_node(name="models.user::User::display_name")
```

---

## find_dependencies

Follow edges forward from a node to find everything it depends on, transitively.
Useful for understanding what a piece of code needs to work.

**Parameters:**
- `name` (str, required) — Name or qualified name of the starting node.
- `edge_kinds` (list[str], optional) — Filter to specific edge types: `imports`, `calls`, `inherits`, `contains`, `depends_on`.
- `max_depth` (int, default `5`) — How many hops to follow.

**Returns:**
```json
{
  "found": true,
  "source": { "id": 42, "qualified_name": "services.user::UserService" },
  "count": 15,
  "dependencies": [
    {
      "id": 43, "kind": "class", "name": "User", "qualified_name": "models::User",
      "file_path": "models.py", "start_line": 5, "end_line": 30, "language": "python",
      "summary": "Core user data model", "annotation_status": "annotated",
      "tags": ["models", "database"], "role": "Data model",
      "depth": 1
    },
    ...
  ]
}
```

**Examples:**
```
"What does UserService depend on?"
→ find_dependencies(name="UserService", max_depth=3)

"Show me all imports for this module"
→ find_dependencies(name="UserService", edge_kinds=["imports"], max_depth=1)

"Full dependency tree for the auth module"
→ find_dependencies(name="auth", max_depth=5)
```

---

## find_dependents

Follow edges backward to find everything that depends on a node. This is your
impact analysis tool — use it before making changes to understand blast radius.

**Parameters:**
- `name` (str, required) — Name or qualified name of the target node.
- `edge_kinds` (list[str], optional) — Filter to specific edge types.
- `max_depth` (int, default `5`) — How many hops to follow backward.

**Returns:**
```json
{
  "found": true,
  "target": { "id": 10, "qualified_name": "models::User" },
  "count": 8,
  "dependents": [
    {
      "id": 42, "kind": "class", "name": "UserService", "qualified_name": "services.user::UserService",
      "file_path": "services/user.py", "start_line": 15, "end_line": 89, "language": "python",
      "summary": "Handles user CRUD with caching", "annotation_status": "annotated",
      "tags": ["service", "database"], "role": "Business logic layer",
      "depth": 1
    },
    ...
  ]
}
```

**Examples:**
```
"What would break if I renamed the User class?"
→ find_dependents(name="User", max_depth=5)

"What calls this function?"
→ find_dependents(name="helper_function", edge_kinds=["calls"])

"Who imports this module?"
→ find_dependents(name="utils.validators", edge_kinds=["imports"])
```

---

## search

Full-text search across node names and LLM-generated summaries. Returns ranked results.
Most useful after annotation has enriched nodes with summaries and tags.

**Parameters:**
- `query` (str, required) — Search terms.
- `kind` (str, optional) — Filter by node kind: `class`, `function`, `method`, `module`, `variable`.
- `limit` (int, default `20`) — Maximum results to return.

**Returns:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 12, "kind": "class", "name": "AuthMiddleware",
      "qualified_name": "middleware::AuthMiddleware",
      "summary": "Validates JWT tokens...", "annotation_status": "annotated",
      "tags": ["auth", "middleware"], "role": "Security layer", ...
    },
    ...
  ]
}
```

**Examples:**
```
"Find all authentication-related code"
→ search(query="authentication")

"Find all service classes"
→ search(query="service", kind="class")

"Find everything related to payment processing"
→ search(query="payment processing")
```

**Note:** Search quality depends on annotation. If `annotation_status` shows many pending
nodes, run the annotation workflow first (see `annotation-workflow.md`).

---

## get_file_structure

Get all definitions in a file with their relationships. This is your "read the table of
contents" tool — use it before editing a file you're unfamiliar with.

**Parameters:**
- `file_path` (str, required) — Path to the file (relative to project root).

**Returns:**
```json
{
  "found": true,
  "file_path": "src/services/user_service.py",
  "nodes": [
    {
      "id": 42, "kind": "class", "name": "UserService", "qualified_name": "services.user::UserService",
      "summary": "Handles user CRUD with caching", "annotation_status": "annotated",
      "tags": ["service", "database"], "role": "Business logic layer",
      "edges": [
        { "direction": "outgoing", "kind": "imports", "target_id": 10 },
        { "direction": "incoming", "kind": "calls", "source_id": 88 }
      ]
    },
    ...
  ]
}
```

**Examples:**
```
"Show me what's in user_service.py"
→ get_file_structure(file_path="src/services/user_service.py")

"What does this file define?"
→ get_file_structure(file_path="app/models.py")
```

---

## annotation_status

Reports how many nodes are pending, annotated, or failed. Use this to check if
semantic search will return good results.

**Parameters:** None.

**Returns:**
```json
{
  "pending": 45,
  "annotated": 120,
  "failed": 2,
  "stale": 8,
  "annotation_running": false
}
```

`stale` counts annotated nodes whose source code has changed since annotation. These nodes
have summaries that may no longer be accurate. Use `find_stale_annotations()` to list them
and re-annotate.

**When to use:** After indexing, or before relying on `search` for semantic queries.

---

## get_pending_annotations

Returns a batch of nodes needing annotation with their source code, metadata,
and neighbor context. The agent uses this to understand what each node does and
generate appropriate summaries and tags.

**Parameters:**
- `batch_size` (int, default `10`) — Maximum nodes to return.

**Returns:**
```json
{
  "batch": [
    {
      "qualified_name": "services.user::UserService",
      "kind": "class",
      "source_code": "class UserService:\n    ...",
      "file_path": "src/services/user_service.py",
      "start_line": 15,
      "end_line": 89,
      "neighbors": [ ... ]
    },
    ...
  ],
  "taxonomy": ["authentication", "database", "api", "validation", ...],
  "count": 10
}
```

---

## submit_annotations

Write annotation results for nodes. Each annotation includes a summary, tags, and role.

**Parameters:**
- `annotations` (list[dict], required) — Each dict should contain:
  - `qualified_name` (str) — identifies the node
  - `summary` (str) — one-sentence summary of what the node does
  - `tags` (list[str]) — suggested tags from the taxonomy or new ones
  - `role` (str) — short role description (e.g. "Input validator", "Data access layer")
  - `failed` (bool, optional) — set `true` to mark as failed instead of annotated

**Returns:**
```json
{
  "written": 8,
  "failed": 1,
  "skipped": 1
}
```

On successful writes, `submit_annotations` sets `annotated_content_hash` on each node to
match its current `content_hash`. This is how staleness detection works — if the source
changes later, the hashes diverge and `find_stale_annotations()` picks it up.

**Example:**
```
submit_annotations(annotations=[
  {
    "qualified_name": "services.user::UserService",
    "summary": "Handles user CRUD operations with validation and caching",
    "tags": ["service", "database", "validation"],
    "role": "Business logic layer"
  },
  {
    "qualified_name": "utils.helpers::format_date",
    "summary": "Formats datetime objects to ISO 8601 strings",
    "tags": ["formatting", "utility"],
    "role": "Formatting utility"
  }
])
```

---

## graph_diff

Returns the structural diff from the last indexing run. Shows exactly what nodes and edges
were added, removed, or modified. Call this immediately after `index_codebase()` when
`diff_available` is `true`.

**Parameters:**
- `file_paths` (list[str] | None, default `None`) — Scope the diff to specific files. `None` returns the full diff.
- `include_edges` (bool, default `true`) — Include edge-level changes in the diff.

**Returns:**
```json
{
  "nodes_added": [
    { "qualified_name": "services.payment::PaymentService", "kind": "class", "file_path": "services/payment.py" }
  ],
  "nodes_removed": [
    { "qualified_name": "services.billing::OldBilling", "kind": "class", "file_path": "services/billing.py" }
  ],
  "nodes_modified": [
    { "qualified_name": "services.user::UserService", "kind": "class", "file_path": "services/user.py" }
  ],
  "edges_added": [
    { "source": "services.payment::PaymentService", "target": "models::Invoice", "kind": "imports" }
  ],
  "edges_removed": [
    { "source": "services.billing::OldBilling", "target": "models::Invoice", "kind": "imports" }
  ],
  "summary": "3 nodes added, 1 removed, 2 modified, 4 edges added, 2 edges removed"
}
```

**When to use:** After `index_codebase()` to understand what changed structurally. Use
the diff to decide which areas need review, re-annotation, or impact analysis.

**When NOT to use:** Before indexing (there is no diff to return), or when you only need
to check a specific node (use `query_node` instead).

**Examples:**
```
"What changed in the last index?"
-> graph_diff()

"Show me what changed in the services directory"
-> graph_diff(file_paths=["services/user.py", "services/payment.py"])

"Just show me node changes, skip edges"
-> graph_diff(include_edges=false)
```

---

## validate_graph

Run structural health checks on the graph. Detects orphan nodes, dangling edges,
and stale annotations that could degrade query quality.

**Parameters:**
- `scope` (list[str] | None, default `None`) — Limit checks to specific file paths. `None` checks the entire graph.
- `checks` (list[str] | None, default `None`) — Run only specific checks. `None` runs all available checks.
  Available checks: `dangling_edges`, `orphan_nodes`, `stale_annotations`.

**Returns:**
```json
{
  "passed": false,
  "issues": [
    {
      "check": "dangling_edges",
      "severity": "error",
      "message": "Edge from services.user::UserService -> models::DeletedModel references non-existent target",
      "source": "services.user::UserService",
      "target": "models::DeletedModel"
    },
    {
      "check": "orphan_nodes",
      "severity": "warning",
      "message": "Node utils.legacy::old_helper has no incoming or outgoing edges",
      "node": "utils.legacy::old_helper"
    },
    {
      "check": "stale_annotations",
      "severity": "warning",
      "message": "12 nodes have annotations that predate their last source change",
      "count": 12
    }
  ],
  "summary": {
    "checks_run": 3,
    "errors": 1,
    "warnings": 2,
    "passed": false
  }
}
```

**When to use:** After indexing to verify graph integrity, before relying on search
results, or as part of a review workflow to catch structural issues.

**When NOT to use:** For querying specific nodes or relationships (use `query_node`,
`find_dependencies`, `find_dependents` instead).

**Examples:**
```
"Is the graph healthy?"
-> validate_graph()

"Check just the services directory for issues"
-> validate_graph(scope=["services/user.py", "services/payment.py"])

"Are there any dangling edges?"
-> validate_graph(checks=["dangling_edges"])
```

---

## batch_query_nodes

Query multiple nodes in a single call. Returns all found nodes with their neighbors,
plus a list of names that were not found. More efficient than calling `query_node`
repeatedly.

**Parameters:**
- `names` (list[str], required) — List of names or qualified names to look up.
- `include_neighbors` (bool, default `true`) — Include immediate neighbors for each found node.

**Returns:**
```json
{
  "found": 3,
  "not_found": ["NonExistentClass"],
  "nodes": [
    {
      "id": 42, "kind": "class", "name": "UserService",
      "qualified_name": "services.user::UserService",
      "file_path": "services/user.py", "start_line": 15, "end_line": 89,
      "language": "python", "summary": "Handles user CRUD with caching",
      "annotation_status": "annotated",
      "tags": ["service", "database"], "role": "Business logic layer",
      "neighbors": [
        { "direction": "outgoing", "edge_kind": "imports", "node": { "...same fields..." } }
      ]
    },
    ...
  ]
}
```

**When to use:** When you need context on multiple symbols at once — e.g., all nodes
from a diff, all classes in a module, or a set of related functions. Saves round-trips
compared to repeated `query_node` calls.

**When NOT to use:** For a single node lookup (use `query_node`). For discovering nodes
by keyword (use `search`).

**Examples:**
```
"Look up these three classes together"
-> batch_query_nodes(names=["UserService", "PaymentService", "AuthMiddleware"])

"Get info on these nodes without neighbors"
-> batch_query_nodes(names=["utils.helpers::format_date", "models::User"], include_neighbors=false)
```

---

## get_context_summary

Token-efficient context summary for agent consumption. Groups nodes by file with
in-degree scores, optimized for fitting maximum structural context into limited
token budgets.

**Parameters:**
- `file_paths` (list[str] | None, default `None`) — Scope to specific files.
- `qualified_names` (list[str] | None, default `None`) — Scope to specific nodes.
- `include_edges` (bool, default `false`) — Include edge relationships between nodes.
- `max_nodes` (int, default `50`) — Maximum number of nodes to return (highest in-degree first).

**Returns:**
```json
{
  "total_nodes": 35,
  "groups": {
    "services/user.py": [
      {
        "qualified_name": "services.user::UserService", "kind": "class",
        "summary": "Handles user CRUD with caching",
        "role": "Business logic layer", "in_degree": 12
      },
      {
        "qualified_name": "services.user::UserService::create_user", "kind": "method",
        "summary": "Creates a new user with validation",
        "role": "Entry point", "in_degree": 5
      }
    ],
    "models/user.py": [
      ...
    ]
  },
  "edges": [
    { "source": "services.user::UserService", "target": "models::User", "kind": "imports" }
  ]
}
```

**When to use:** When building context for agent dispatch — plan, work, review, and
brainstorm orchestrators use this to provide structural context without exhausting token
budgets. Prefer this over multiple `query_node` calls when you need an overview.

**When NOT to use:** When you need full node details with source code (use `query_node`
or `get_file_structure`). When you need transitive dependencies (use `find_dependencies`
or `find_dependents`).

**Examples:**
```
"Summarize the structure of these files for the agent"
-> get_context_summary(file_paths=["services/user.py", "models/user.py"], include_edges=true)

"Get context on the top 20 most-connected nodes"
-> get_context_summary(max_nodes=20)

"Context for specific symbols"
-> get_context_summary(qualified_names=["UserService", "PaymentService", "models::User"])
```

---

## find_stale_annotations

Find nodes whose source code has changed since they were last annotated. These nodes
have summaries, tags, and roles that may no longer be accurate.

**Parameters:**
- `file_paths` (list[str] | None, default `None`) — Scope to specific files. `None` checks the entire graph.
- `limit` (int, default `50`) — Maximum number of stale nodes to return.

**Returns:**
```json
{
  "count": 8,
  "stale_nodes": [
    {
      "id": 42, "kind": "class", "name": "UserService",
      "qualified_name": "services.user::UserService",
      "file_path": "services/user.py", "start_line": 15, "end_line": 89,
      "language": "python",
      "summary": "Handles user CRUD with caching",
      "annotation_status": "annotated",
      "tags": ["service", "database"], "role": "Business logic layer",
      "reason": "content_hash_changed"
    },
    ...
  ]
}
```

**When to use:** After indexing changed files to discover which annotations need
refreshing. Part of the stale annotation re-annotation workflow (see
`annotation-workflow.md`).

**When NOT to use:** To find nodes that have never been annotated (use
`annotation_status` and `get_pending_annotations` instead).

**Examples:**
```
"Which annotations are outdated?"
-> find_stale_annotations()

"Check if annotations in the services directory are stale"
-> find_stale_annotations(file_paths=["services/user.py", "services/payment.py"])

"Get the top 10 most urgently stale nodes"
-> find_stale_annotations(limit=10)
```

---

## rank_nodes

Score nodes by structural importance. Identifies the most-connected, most-depended-upon
symbols in the codebase or a subset of it.

**Parameters:**
- `scope` (list[str] | None, default `None`) — Limit ranking to specific file paths. `None` ranks the entire graph.
- `kind` (str | None, default `None`) — Filter by node kind: `class`, `function`, `method`, `module`, `variable`.
- `limit` (int, default `20`) — Maximum number of ranked nodes to return.
- `algorithm` (str, default `"in_degree"`) — Ranking algorithm to use. Currently supports `in_degree`.

**Returns:**
```json
{
  "ranked": [
    {
      "id": 10, "kind": "class", "name": "User",
      "qualified_name": "models::User",
      "file_path": "models/user.py", "start_line": 5, "end_line": 30,
      "language": "python",
      "summary": "Core user data model",
      "annotation_status": "annotated",
      "tags": ["model", "database"], "role": "Data model",
      "score": 24, "in_degree": 24, "out_degree": 3
    },
    {
      "id": 42, "kind": "class", "name": "UserService",
      "qualified_name": "services.user::UserService",
      "file_path": "services/user.py", "start_line": 15, "end_line": 89,
      "language": "python",
      "summary": "Handles user CRUD with caching",
      "annotation_status": "annotated",
      "tags": ["service", "database"], "role": "Business logic layer",
      "score": 18, "in_degree": 18, "out_degree": 7
    },
    ...
  ]
}
```

**When to use:** To identify high-impact nodes before refactoring, to prioritize
annotation effort on the most important symbols, or to understand the structural
backbone of a codebase.

**When NOT to use:** For finding nodes by name or keyword (use `search` or `query_node`).
For understanding a specific node's relationships (use `find_dependencies` or
`find_dependents`).

**Examples:**
```
"What are the most important classes in this codebase?"
-> rank_nodes(kind="class", limit=10)

"Rank all nodes in the services directory"
-> rank_nodes(scope=["services/user.py", "services/payment.py"])

"Top 5 most-depended-upon functions"
-> rank_nodes(kind="function", limit=5)
```
