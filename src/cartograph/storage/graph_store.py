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
                                   annotation_status, content_hash, properties)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                INSERT INTO edges (source_id, target_id, kind, weight, properties)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
                    weight = excluded.weight,
                    properties = excluded.properties
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
                                       annotation_status, content_hash, properties)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    INSERT INTO edges (source_id, target_id, kind, weight, properties)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(source_id, target_id, kind) DO UPDATE SET
                        weight = excluded.weight,
                        properties = excluded.properties
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
    # Utility
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
