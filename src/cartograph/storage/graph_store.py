"""High-level graph store backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from typing import Any


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a plain dict, deserialising JSON properties."""
    d = dict(row)
    if "properties" in d and d["properties"] is not None:
        try:
            d["properties"] = json.loads(d["properties"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


class GraphStore:
    """CRUD and traversal API over the Cartograph SQLite graph."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._conn = connection

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    def upsert_nodes(self, nodes: list[dict]) -> list[int]:
        """Insert or update nodes using qualified_name as conflict key.

        Returns the list of node IDs (in the same order as *nodes*).
        """
        ids: list[int] = []
        for node in nodes:
            props = node.get("properties")
            if props is not None and not isinstance(props, str):
                props = json.dumps(props)
            cur = self._conn.execute(
                """
                INSERT INTO nodes (kind, name, qualified_name, file_path,
                                   start_line, end_line, language, summary,
                                   annotation_status, content_hash, properties,
                                   annotated_content_hash, graph_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(qualified_name) DO UPDATE SET
                    kind = excluded.kind,
                    name = excluded.name,
                    file_path = excluded.file_path,
                    start_line = excluded.start_line,
                    end_line = excluded.end_line,
                    language = excluded.language,
                    summary = CASE
                        WHEN nodes.annotation_status IN ('annotated', 'failed')
                             AND excluded.annotation_status = 'pending'
                        THEN nodes.summary
                        ELSE excluded.summary
                    END,
                    annotation_status = CASE
                        WHEN nodes.annotation_status IN ('annotated', 'failed')
                             AND excluded.annotation_status = 'pending'
                        THEN nodes.annotation_status
                        ELSE excluded.annotation_status
                    END,
                    content_hash = excluded.content_hash,
                    properties = CASE
                        WHEN nodes.annotation_status IN ('annotated', 'failed')
                             AND excluded.annotation_status = 'pending'
                        THEN nodes.properties
                        ELSE excluded.properties
                    END,
                    annotated_content_hash = CASE
                        WHEN nodes.annotation_status IN ('annotated', 'failed')
                             AND excluded.annotation_status = 'pending'
                        THEN nodes.annotated_content_hash
                        ELSE excluded.annotated_content_hash
                    END,
                    graph_version = excluded.graph_version,
                    updated_at = datetime('now')
                """,
                (
                    node["kind"],
                    node["name"],
                    node["qualified_name"],
                    node["file_path"],
                    node.get("start_line"),
                    node.get("end_line"),
                    node.get("language"),
                    node.get("summary"),
                    node.get("annotation_status", "pending"),
                    node.get("content_hash"),
                    props,
                    node.get("annotated_content_hash"),
                    node.get("graph_version", 0),
                ),
            )
            ids.append(cur.lastrowid)  # type: ignore[arg-type]
        self._conn.commit()
        return ids

    def get_node(self, node_id: int) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def get_node_by_name(self, qualified_name: str) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT * FROM nodes WHERE qualified_name = ?", (qualified_name,))
        row = cur.fetchone()
        return _row_to_dict(row) if row else None

    def find_nodes(
        self,
        kind: str | None = None,
        file_path: str | None = None,
        name: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        if file_path is not None:
            clauses.append("file_path = ?")
            params.append(file_path)
        if name is not None:
            clauses.append("name = ?")
            params.append(name)
        where = " AND ".join(clauses) if clauses else "1=1"
        cur = self._conn.execute(f"SELECT * FROM nodes WHERE {where}", params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def upsert_edges(self, edges: list[dict]) -> None:
        """Insert or update edges (source_id, target_id, kind as conflict key)."""
        for edge in edges:
            props = edge.get("properties")
            if props is not None and not isinstance(props, str):
                props = json.dumps(props)
            self._conn.execute(
                """
                INSERT INTO edges (source_id, target_id, kind, weight, properties,
                                   updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
                    weight = excluded.weight,
                    properties = excluded.properties,
                    updated_at = datetime('now')
                """,
                (
                    edge["source_id"],
                    edge["target_id"],
                    edge["kind"],
                    edge.get("weight", 1.0),
                    props,
                ),
            )
        self._conn.commit()

    def get_edges(
        self,
        source_id: int | None = None,
        target_id: int | None = None,
        kind: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        if target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)
        where = " AND ".join(clauses) if clauses else "1=1"
        cur = self._conn.execute(f"SELECT * FROM edges WHERE {where}", params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Graph traversal (recursive CTEs)
    # ------------------------------------------------------------------

    def transitive_dependencies(
        self,
        node_id: int,
        edge_kinds: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[dict[str, Any]]:
        """Follow edges forward from *node_id*. Return reachable nodes with depth."""
        kind_filter = ""
        if edge_kinds:
            placeholders = ", ".join("?" for _ in edge_kinds)
            kind_filter = f"AND e.kind IN ({placeholders})"

        # Build the parameter list for the CTE.  The edge_kinds params appear
        # twice (once in the seed, once in the recursive step).
        if edge_kinds:
            all_params: list[Any] = [node_id] + list(edge_kinds) + list(edge_kinds) + [max_depth]
        else:
            all_params = [node_id, max_depth]

        sql = f"""
            WITH RECURSIVE deps(node_id, depth) AS (
                SELECT e.target_id, 1
                FROM edges e
                WHERE e.source_id = ? {kind_filter}
              UNION
                SELECT e.target_id, d.depth + 1
                FROM deps d
                JOIN edges e ON e.source_id = d.node_id {kind_filter}
                WHERE d.depth < ?
            )
            SELECT n.*, d.depth
            FROM deps d
            JOIN nodes n ON n.id = d.node_id
            ORDER BY d.depth
        """
        cur = self._conn.execute(sql, all_params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    def reverse_dependencies(
        self,
        node_id: int,
        edge_kinds: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[dict[str, Any]]:
        """Follow edges backward to *node_id* (impact analysis)."""
        kind_filter = ""
        if edge_kinds:
            placeholders = ", ".join("?" for _ in edge_kinds)
            kind_filter = f"AND e.kind IN ({placeholders})"

        if edge_kinds:
            all_params: list[Any] = [node_id] + list(edge_kinds) + list(edge_kinds) + [max_depth]
        else:
            all_params = [node_id, max_depth]

        sql = f"""
            WITH RECURSIVE rdeps(node_id, depth) AS (
                SELECT e.source_id, 1
                FROM edges e
                WHERE e.target_id = ? {kind_filter}
              UNION
                SELECT e.source_id, d.depth + 1
                FROM rdeps d
                JOIN edges e ON e.target_id = d.node_id {kind_filter}
                WHERE d.depth < ?
            )
            SELECT n.*, d.depth
            FROM rdeps d
            JOIN nodes n ON n.id = d.node_id
            ORDER BY d.depth
        """
        cur = self._conn.execute(sql, all_params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """FTS5 search across node names and summaries. Returns ranked results."""
        params: list[Any] = [query]
        kind_clause = ""
        if kind is not None:
            kind_clause = "AND n.kind = ?"
            params.append(kind)
        params.append(limit)
        sql = f"""
            SELECT n.*, rank
            FROM nodes_fts fts
            JOIN nodes n ON n.id = fts.rowid
            WHERE nodes_fts MATCH ?
            {kind_clause}
            ORDER BY rank
            LIMIT ?
        """
        cur = self._conn.execute(sql, params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Stale annotation detection
    # ------------------------------------------------------------------

    def find_stale_nodes(
        self,
        file_paths: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Find annotated nodes whose content has changed since annotation.

        A node is stale when ``annotation_status = 'annotated'`` and either
        ``annotated_content_hash`` is NULL (pre-migration node) or it differs
        from the current ``content_hash``.
        """
        clauses: list[str] = [
            "annotation_status = 'annotated'",
            "content_hash IS NOT NULL",
            "(annotated_content_hash IS NULL OR content_hash != annotated_content_hash)",
        ]
        params: list[Any] = []
        if file_paths:
            placeholders = ", ".join("?" for _ in file_paths)
            clauses.append(f"file_path IN ({placeholders})")
            params.extend(file_paths)
        params.append(limit)
        where = " AND ".join(clauses)
        cur = self._conn.execute(
            f"SELECT * FROM nodes WHERE {where} LIMIT ?",
            params,  # noqa: S608
        )
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Context summary
    # ------------------------------------------------------------------

    def context_summary(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
        max_nodes: int = 50,
    ) -> list[dict[str, Any]]:
        """Return nodes with in_degree counts, filtered by file paths or qualified names.

        Results are ordered by in_degree descending and limited to *max_nodes*.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if file_paths:
            placeholders = ", ".join("?" for _ in file_paths)
            clauses.append(f"n.file_path IN ({placeholders})")
            params.extend(file_paths)
        if qualified_names:
            placeholders = ", ".join("?" for _ in qualified_names)
            clauses.append(f"n.qualified_name IN ({placeholders})")
            params.extend(qualified_names)

        where = " AND ".join(clauses) if clauses else "1=1"
        params.append(max_nodes)

        sql = f"""
            SELECT n.*, COALESCE(ec.cnt, 0) AS in_degree
            FROM nodes n
            LEFT JOIN (
                SELECT target_id, COUNT(*) AS cnt
                FROM edges
                GROUP BY target_id
            ) ec ON ec.target_id = n.id
            WHERE {where}
            ORDER BY in_degree DESC
            LIMIT ?
        """
        cur = self._conn.execute(sql, params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_by_in_degree(
        self,
        scope_file_paths: list[str] | None = None,
        scope_qnames: list[str] | None = None,
        kind: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return nodes ranked by incoming edge count (in-degree).

        Each returned dict has extra keys ``in_degree`` and ``out_degree``.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if scope_file_paths:
            placeholders = ", ".join("?" for _ in scope_file_paths)
            clauses.append(f"n.file_path IN ({placeholders})")
            params.extend(scope_file_paths)

        if scope_qnames:
            placeholders = ", ".join("?" for _ in scope_qnames)
            clauses.append(f"n.qualified_name IN ({placeholders})")
            params.extend(scope_qnames)

        if kind is not None:
            clauses.append("n.kind = ?")
            params.append(kind)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)

        sql = f"""
            SELECT n.*,
                   COUNT(e.id) AS in_degree,
                   (SELECT COUNT(*) FROM edges e2 WHERE e2.source_id = n.id) AS out_degree
            FROM nodes n
            LEFT JOIN edges e ON e.target_id = n.id
            {where}
            GROUP BY n.id
            ORDER BY in_degree DESC
            LIMIT ?
        """
        cur = self._conn.execute(sql, params)
        return [_row_to_dict(r) for r in cur.fetchall()]

    def rank_by_transitive(
        self,
        scope_qnames: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Return nodes ranked by transitive reverse-dependency count.

        If *scope_qnames* is provided, only those nodes are considered.
        Otherwise all nodes are considered (capped at 50 to avoid expensive
        recursive queries).
        """
        if scope_qnames:
            nodes: list[dict[str, Any]] = []
            for qn in scope_qnames[:50]:
                node = self.get_node_by_name(qn)
                if node is not None:
                    nodes.append(node)
        else:
            # Grab top candidates by raw in-degree first, then refine.
            nodes = self.rank_by_in_degree(limit=50)

        scored: list[dict[str, Any]] = []
        for node in nodes:
            rdeps = self.reverse_dependencies(node["id"])
            node_copy = dict(node)
            node_copy["transitive_count"] = len(rdeps)
            scored.append(node_copy)

        scored.sort(key=lambda n: n["transitive_count"], reverse=True)
        return scored[:limit]

    # ------------------------------------------------------------------
    # Re-indexing support
    # ------------------------------------------------------------------

    def delete_file_nodes(self, file_path: str) -> int:
        """Delete all nodes for a file. Cascading deletes remove edges."""
        cur = self._conn.execute("DELETE FROM nodes WHERE file_path = ?", (file_path,))
        self._conn.commit()
        return cur.rowcount

    def get_content_hashes(self) -> dict[str, str]:
        """Return {file_path: content_hash} for all file nodes."""
        cur = self._conn.execute(
            "SELECT file_path, content_hash FROM nodes WHERE kind = 'file' AND content_hash IS NOT NULL"
        )
        return {row["file_path"]: row["content_hash"] for row in cur.fetchall()}

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def bulk_insert_nodes(self, nodes: list[dict]) -> list[int]:
        """Batch insert nodes in a single transaction for performance."""
        ids: list[int] = []
        with self._conn:
            for node in nodes:
                props = node.get("properties")
                if props is not None and not isinstance(props, str):
                    props = json.dumps(props)
                cur = self._conn.execute(
                    """
                    INSERT INTO nodes (kind, name, qualified_name, file_path,
                                       start_line, end_line, language, summary,
                                       annotation_status, content_hash, properties,
                                       annotated_content_hash, graph_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(qualified_name) DO UPDATE SET
                        kind = excluded.kind,
                        name = excluded.name,
                        file_path = excluded.file_path,
                        start_line = excluded.start_line,
                        end_line = excluded.end_line,
                        language = excluded.language,
                        summary = CASE
                            WHEN nodes.annotation_status IN ('annotated', 'failed')
                                 AND excluded.annotation_status = 'pending'
                            THEN nodes.summary
                            ELSE excluded.summary
                        END,
                        annotation_status = CASE
                            WHEN nodes.annotation_status IN ('annotated', 'failed')
                                 AND excluded.annotation_status = 'pending'
                            THEN nodes.annotation_status
                            ELSE excluded.annotation_status
                        END,
                        content_hash = excluded.content_hash,
                        properties = CASE
                            WHEN nodes.annotation_status IN ('annotated', 'failed')
                                 AND excluded.annotation_status = 'pending'
                            THEN nodes.properties
                            ELSE excluded.properties
                        END,
                        annotated_content_hash = CASE
                            WHEN nodes.annotation_status IN ('annotated', 'failed')
                                 AND excluded.annotation_status = 'pending'
                            THEN nodes.annotated_content_hash
                            ELSE excluded.annotated_content_hash
                        END,
                        graph_version = excluded.graph_version,
                        updated_at = datetime('now')
                    """,
                    (
                        node["kind"],
                        node["name"],
                        node["qualified_name"],
                        node["file_path"],
                        node.get("start_line"),
                        node.get("end_line"),
                        node.get("language"),
                        node.get("summary"),
                        node.get("annotation_status", "pending"),
                        node.get("content_hash"),
                        props,
                        node.get("annotated_content_hash"),
                        node.get("graph_version", 0),
                    ),
                )
                ids.append(cur.lastrowid)  # type: ignore[arg-type]
        return ids

    def bulk_insert_edges(self, edges: list[dict]) -> None:
        """Batch insert edges in a single transaction."""
        with self._conn:
            for edge in edges:
                props = edge.get("properties")
                if props is not None and not isinstance(props, str):
                    props = json.dumps(props)
                self._conn.execute(
                    """
                    INSERT INTO edges (source_id, target_id, kind, weight, properties,
                                       updated_at)
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
                        weight = excluded.weight,
                        properties = excluded.properties,
                        updated_at = datetime('now')
                    """,
                    (
                        edge["source_id"],
                        edge["target_id"],
                        edge["kind"],
                        edge.get("weight", 1.0),
                        props,
                    ),
                )

    # ------------------------------------------------------------------
    # Graph versioning
    # ------------------------------------------------------------------

    def get_graph_version(self) -> int:
        """Return the current graph version counter."""
        row = self._conn.execute("SELECT graph_version FROM graph_meta WHERE id = 1").fetchone()
        return int(row[0]) if row else 0

    def increment_graph_version(self) -> int:
        """Atomically increment and return the new graph version."""
        self._conn.execute("UPDATE graph_meta SET graph_version = graph_version + 1 WHERE id = 1")
        self._conn.commit()
        return self.get_graph_version()

    # ------------------------------------------------------------------
    # Diff support
    # ------------------------------------------------------------------

    def snapshot_nodes(self, file_paths: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """Return a snapshot of {qualified_name: {kind, name, file_path, content_hash}}.

        If *file_paths* is provided, only snapshot nodes belonging to those files.
        Otherwise snapshot all nodes.
        """
        if file_paths is not None:
            placeholders = ", ".join("?" for _ in file_paths)
            sql = f"""
                SELECT qualified_name, kind, name, file_path, content_hash
                FROM nodes WHERE file_path IN ({placeholders})
            """
            cur = self._conn.execute(sql, file_paths)
        else:
            cur = self._conn.execute(
                "SELECT qualified_name, kind, name, file_path, content_hash FROM nodes"
            )
        return {row["qualified_name"]: dict(row) for row in cur.fetchall()}

    def snapshot_edges(self, file_paths: list[str] | None = None) -> list[dict[str, Any]]:
        """Return a snapshot of edges as [{source, target, kind}].

        Uses qualified_name as the stable key (not node IDs which change
        across delete/reinsert).  If *file_paths* is given, limit to edges
        where at least one endpoint belongs to those files.
        """
        if file_paths is not None:
            placeholders = ", ".join("?" for _ in file_paths)
            sql = f"""
                SELECT sn.qualified_name AS source, tn.qualified_name AS target, e.kind
                FROM edges e
                JOIN nodes sn ON sn.id = e.source_id
                JOIN nodes tn ON tn.id = e.target_id
                WHERE sn.file_path IN ({placeholders}) OR tn.file_path IN ({placeholders})
            """
            cur = self._conn.execute(sql, list(file_paths) + list(file_paths))
        else:
            cur = self._conn.execute("""
                SELECT sn.qualified_name AS source, tn.qualified_name AS target, e.kind
                FROM edges e
                JOIN nodes sn ON sn.id = e.source_id
                JOIN nodes tn ON tn.id = e.target_id
            """)
        return [dict(row) for row in cur.fetchall()]

    def compute_diff(
        self,
        before_nodes: dict[str, dict[str, Any]],
        after_nodes: dict[str, dict[str, Any]],
        before_edges: list[dict[str, Any]],
        after_edges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute a structural diff between two snapshots.

        Returns the canonical diff dict with nodes_added, nodes_removed,
        nodes_modified, edges_added, edges_removed, and summary.
        """
        before_qnames = set(before_nodes)
        after_qnames = set(after_nodes)

        added_qnames = after_qnames - before_qnames
        removed_qnames = before_qnames - after_qnames
        common_qnames = before_qnames & after_qnames

        nodes_added = [
            {
                "qualified_name": qn,
                "kind": after_nodes[qn]["kind"],
                "name": after_nodes[qn]["name"],
                "file_path": after_nodes[qn]["file_path"],
            }
            for qn in sorted(added_qnames)
        ]

        nodes_removed = [
            {
                "qualified_name": qn,
                "kind": before_nodes[qn]["kind"],
                "name": before_nodes[qn]["name"],
                "file_path": before_nodes[qn]["file_path"],
            }
            for qn in sorted(removed_qnames)
        ]

        nodes_modified = []
        for qn in sorted(common_qnames):
            changes: list[str] = []
            if before_nodes[qn].get("content_hash") != after_nodes[qn].get("content_hash"):
                changes.append("content_hash_changed")
            if changes:
                nodes_modified.append(
                    {
                        "qualified_name": qn,
                        "kind": after_nodes[qn]["kind"],
                        "file_path": after_nodes[qn]["file_path"],
                        "changes": changes,
                    }
                )

        # Edge diff using (source, target, kind) tuples.
        before_edge_set = {(e["source"], e["target"], e["kind"]) for e in before_edges}
        after_edge_set = {(e["source"], e["target"], e["kind"]) for e in after_edges}

        edges_added = [
            {"source": s, "target": t, "kind": k}
            for s, t, k in sorted(after_edge_set - before_edge_set)
        ]
        edges_removed = [
            {"source": s, "target": t, "kind": k}
            for s, t, k in sorted(before_edge_set - after_edge_set)
        ]

        files_affected: set[str] = set()
        for lst in (nodes_added, nodes_removed, nodes_modified):
            for n in lst:
                if n.get("file_path"):
                    files_affected.add(n["file_path"])

        return {
            "nodes_added": nodes_added,
            "nodes_removed": nodes_removed,
            "nodes_modified": nodes_modified,
            "edges_added": edges_added,
            "edges_removed": edges_removed,
            "summary": {
                "files_affected": len(files_affected),
                "nodes_added": len(nodes_added),
                "nodes_removed": len(nodes_removed),
                "nodes_modified": len(nodes_modified),
                "edges_added": len(edges_added),
                "edges_removed": len(edges_removed),
            },
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_nodes(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
        checks: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Run integrity checks on the graph and return a list of issues.

        Each issue is a dict with at least ``check``, ``severity``, and
        ``message`` keys.  Additional keys depend on the check type.

        Parameters
        ----------
        file_paths:
            Limit scope to nodes belonging to these files.
        qualified_names:
            Limit scope to these specific qualified names.
        checks:
            Subset of ``"dangling_edges"``, ``"orphan_nodes"``,
            ``"stale_annotations"``.  *None* means run all checks.
        """
        all_checks = {"dangling_edges", "orphan_nodes", "stale_annotations"}
        active = set(checks) & all_checks if checks else all_checks
        issues: list[dict[str, Any]] = []

        if "dangling_edges" in active:
            issues.extend(self._check_dangling_edges(file_paths, qualified_names))
        if "orphan_nodes" in active:
            issues.extend(self._check_orphan_nodes(file_paths, qualified_names))
        if "stale_annotations" in active:
            issues.extend(self._check_stale_annotations(file_paths, qualified_names))

        return issues

    def _check_dangling_edges(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find edges whose source or target node doesn't exist."""
        # With FK constraints + CASCADE this is rare, but we check anyway.
        # We look for edges where LEFT JOIN on source or target yields NULL.
        scope_clause, params = self._build_edge_scope(file_paths, qualified_names)

        sql = f"""
            SELECT e.id, e.kind,
                   sn.qualified_name AS source_qname,
                   tn.qualified_name AS target_qname,
                   e.source_id, e.target_id
            FROM edges e
            LEFT JOIN nodes sn ON sn.id = e.source_id
            LEFT JOIN nodes tn ON tn.id = e.target_id
            WHERE (sn.id IS NULL OR tn.id IS NULL)
            {scope_clause}
        """
        cur = self._conn.execute(sql, params)
        issues: list[dict[str, Any]] = []
        for row in cur.fetchall():
            r = dict(row)
            issues.append(
                {
                    "check": "dangling_edges",
                    "severity": "error",
                    "message": "Edge references non-existent "
                    + ("source" if r["source_qname"] is None else "target")
                    + " node",
                    "source": r["source_qname"] or f"<missing id={r['source_id']}>",
                    "target": r["target_qname"] or f"<missing id={r['target_id']}>",
                    "edge_kind": r["kind"],
                }
            )
        return issues

    def _check_orphan_nodes(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find non-file/module nodes with zero incoming edges."""
        scope_clauses: list[str] = [
            "n.kind NOT IN ('file', 'module')",
        ]
        params: list[Any] = []
        if file_paths:
            placeholders = ", ".join("?" for _ in file_paths)
            scope_clauses.append(f"n.file_path IN ({placeholders})")
            params.extend(file_paths)
        if qualified_names:
            placeholders = ", ".join("?" for _ in qualified_names)
            scope_clauses.append(f"n.qualified_name IN ({placeholders})")
            params.extend(qualified_names)

        where = " AND ".join(scope_clauses)
        sql = f"""
            SELECT n.qualified_name
            FROM nodes n
            LEFT JOIN edges e ON e.target_id = n.id
            WHERE {where}
            GROUP BY n.id
            HAVING COUNT(e.id) = 0
        """
        cur = self._conn.execute(sql, params)
        return [
            {
                "check": "orphan_nodes",
                "severity": "warning",
                "message": "Node has no incoming edges",
                "node": row["qualified_name"],
            }
            for row in cur.fetchall()
        ]

    def _check_stale_annotations(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Find nodes where annotation is outdated (content changed since annotation)."""
        clauses: list[str] = [
            "annotation_status = 'annotated'",
            "content_hash IS NOT NULL",
            "(annotated_content_hash IS NULL OR content_hash != annotated_content_hash)",
        ]
        params: list[Any] = []
        if file_paths:
            placeholders = ", ".join("?" for _ in file_paths)
            clauses.append(f"file_path IN ({placeholders})")
            params.extend(file_paths)
        if qualified_names:
            placeholders = ", ".join("?" for _ in qualified_names)
            clauses.append(f"qualified_name IN ({placeholders})")
            params.extend(qualified_names)

        where = " AND ".join(clauses)
        cur = self._conn.execute(
            f"SELECT qualified_name FROM nodes WHERE {where}",  # noqa: S608
            params,
        )
        return [
            {
                "check": "stale_annotations",
                "severity": "warning",
                "message": "Annotation is outdated",
                "node": row["qualified_name"],
            }
            for row in cur.fetchall()
        ]

    def _build_edge_scope(
        self,
        file_paths: list[str] | None = None,
        qualified_names: list[str] | None = None,
    ) -> tuple[str, list[Any]]:
        """Build a WHERE clause fragment to scope edge checks to relevant nodes."""
        if not file_paths and not qualified_names:
            return "", []

        parts: list[str] = []
        params: list[Any] = []
        if file_paths:
            placeholders = ", ".join("?" for _ in file_paths)
            parts.append(f"(sn.file_path IN ({placeholders}) OR tn.file_path IN ({placeholders}))")
            params.extend(file_paths)
            params.extend(file_paths)
        if qualified_names:
            placeholders = ", ".join("?" for _ in qualified_names)
            parts.append(
                f"(sn.qualified_name IN ({placeholders}) OR tn.qualified_name IN ({placeholders}))"
            )
            params.extend(qualified_names)
            params.extend(qualified_names)

        return "AND (" + " OR ".join(parts) + ")", params

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
