# Tool Reference

Detailed parameters, return values, and examples for all 9 Cartograph MCP tools.

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
  "errors": []
}
```

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
  "node": { "id": 42, "kind": "class", "name": "UserService", "qualified_name": "services.user::UserService", ... },
  "neighbors": [
    { "direction": "outgoing", "edge_kind": "imports", "node": { ... } },
    { "direction": "incoming", "edge_kind": "calls", "node": { ... } }
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
    { "id": 43, "kind": "class", "name": "User", "qualified_name": "models::User", "file_path": "models.py", "depth": 1 },
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
    { "id": 42, "kind": "class", "name": "UserService", "qualified_name": "services.user::UserService", "file_path": "services/user.py", "depth": 1 },
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
    { "id": 12, "kind": "class", "name": "AuthMiddleware", "qualified_name": "middleware::AuthMiddleware", "summary": "Validates JWT tokens...", ... },
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
  "annotation_running": false
}
```

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
