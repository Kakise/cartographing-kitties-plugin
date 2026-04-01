"""Structural indexer: parse files, extract definitions/imports/calls, and store in graph."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cartograph.indexing.discovery import compute_file_hash, detect_changes, discover_files
from cartograph.parsing import (
    CallSite,
    Definition,
    Import,
    ParserRegistry,
    extract_calls,
    extract_definitions,
    extract_imports,
)
from cartograph.storage.graph_store import GraphStore

logger = logging.getLogger(__name__)

# TypeScript/JavaScript extensions for resolution
_TS_JS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx")


@dataclass
class IndexStats:
    """Statistics returned after an indexing run."""

    files_parsed: int = 0
    nodes_created: int = 0
    edges_created: int = 0
    files_deleted: int = 0
    errors: list[str] = field(default_factory=list)


def _module_path_for_file(rel_path: Path, language: str) -> str:
    """Convert a relative file path to a dotted module path (with src/ stripped).

    Python:  src/models/user.py        -> models.user
             src/models/__init__.py     -> models
             models/user.py             -> models.user
    TS/JS:   src/services/user.ts       -> services.user
             services/user.ts           -> services.user
    """
    parts = list(rel_path.parts)

    # Strip leading 'src' directory if present
    if parts and parts[0] == "src":
        parts = parts[1:]

    # Remove file extension from last part
    if parts:
        stem = Path(parts[-1]).stem
        # For Python __init__.py, drop the filename entirely
        if language == "python" and stem == "__init__":
            parts = parts[:-1]
        else:
            parts[-1] = stem

    return ".".join(parts) if parts else ""


def _module_path_for_file_full(rel_path: Path, language: str) -> str:
    """Convert a relative file path to a dotted module path (without stripping src/).

    Python:  src/models/user.py        -> src.models.user
    """
    parts = list(rel_path.parts)

    # Remove file extension from last part
    if parts:
        stem = Path(parts[-1]).stem
        if language == "python" and stem == "__init__":
            parts = parts[:-1]
        else:
            parts[-1] = stem

    return ".".join(parts) if parts else ""


def _resolve_python_import_to_file(
    import_obj: Import,
    file_module_map: dict[str, str],
) -> str | None:
    """Resolve a Python import's module_path to a file_path (relative, as string).

    Returns the file_path string (as stored in nodes) or None if not found.
    """
    module_path = import_obj.module_path

    # For relative imports, resolve relative to the source file's package
    if import_obj.is_relative:
        # Count leading dots
        dots = 0
        for ch in module_path:
            if ch == ".":
                dots += 1
            else:
                break
        relative_module = module_path[dots:]

        # Get the source file's module path to determine current package
        source_rel = import_obj.source_file
        source_parts = Path(source_rel).parts
        # Strip 'src/' prefix
        if source_parts and source_parts[0] == "src":
            source_parts = source_parts[1:]
        # Go up `dots` levels from the source file's directory
        pkg_parts = list(source_parts[:-1])  # directory parts
        for _ in range(dots - 1):
            if pkg_parts:
                pkg_parts.pop()
        if relative_module:
            module_path = (
                ".".join(pkg_parts) + "." + relative_module if pkg_parts else relative_module
            )
        else:
            module_path = ".".join(pkg_parts) if pkg_parts else ""

    # Try exact match first
    if module_path in file_module_map:
        return file_module_map[module_path]

    # Try as package (the module might be a __init__.py)
    # e.g., "models" could map to models/__init__.py
    return None


def _resolve_ts_import_to_file(
    import_obj: Import,
    source_file: str,
    all_files: set[str],
) -> str | None:
    """Resolve a TS/JS relative import to a file path."""
    if not import_obj.is_relative:
        # Bare specifier = external package
        return None

    source_dir = str(Path(source_file).parent)
    raw = import_obj.module_path  # e.g. "./types" or "../utils"

    # Resolve relative path
    candidate = str(Path(source_dir, raw))
    # Normalize
    candidate = str(Path(candidate))

    # Try with various extensions
    for ext in _TS_JS_EXTENSIONS:
        test = candidate + ext
        if test in all_files:
            return test
    # Try /index.ts etc.
    for ext in _TS_JS_EXTENSIONS:
        test = candidate + "/index" + ext
        if test in all_files:
            return test

    return None


class Indexer:
    """Structural indexer: parse source files and populate the graph store."""

    def __init__(self, root_path: Path, graph_store: GraphStore) -> None:
        self.root_path = root_path
        self.graph_store = graph_store
        self.registry = ParserRegistry()

    def index_all(self) -> IndexStats:
        """Full index: discover all files, parse, extract, resolve, store."""
        stats = IndexStats()
        version = self.graph_store.increment_graph_version()
        files = discover_files(self.root_path)
        self._index_files(files, stats, graph_version=version)
        return stats

    def index_changed(self) -> IndexStats:
        """Incremental index: only process changed files."""
        stats = IndexStats()
        version = self.graph_store.increment_graph_version()
        changes = detect_changes(self.root_path, self.graph_store)

        # Delete removed files
        for deleted in changes.deleted:
            count = self.graph_store.delete_file_nodes(str(deleted))
            if count > 0:
                stats.files_deleted += 1

        # Delete then re-index modified files
        for modified in changes.modified:
            self.graph_store.delete_file_nodes(str(modified))
            stats.files_deleted += 1

        # Index new + modified files
        files_to_index = changes.new + changes.modified
        if files_to_index:
            self._index_files(files_to_index, stats, graph_version=version)

        return stats

    def _index_files(self, files: list[Path], stats: IndexStats, *, graph_version: int = 0) -> None:
        """Core indexing logic for a list of files.

        1. Parse each file, extract definitions/imports/calls
        2. Create file + definition nodes, contains edges
        3. Resolve cross-file imports and calls
        """
        # Per-file collected data
        file_definitions: dict[str, list[Definition]] = {}
        file_imports: dict[str, list[Import]] = {}
        file_calls: dict[str, list[CallSite]] = {}
        file_languages: dict[str, str] = {}
        file_node_ids: dict[str, int] = {}  # rel_path_str -> node id
        # qualified_name -> node id for definitions
        def_node_ids: dict[str, int] = {}
        # module_path -> rel_path_str (for Python import resolution)
        module_to_file: dict[str, str] = {}
        # name -> list of (qualified_name, file_path) for name-based resolution
        name_to_defs: dict[str, list[tuple[str, str]]] = {}
        # Set of all relative file path strings
        all_file_strs: set[str] = set()

        # -- Phase 1: Parse all files and create file + definition nodes --
        all_nodes: list[dict[str, Any]] = []
        all_contains_edges: list[tuple[str, str]] = []  # (file_qname, def_qname)
        file_qnames: dict[str, str] = {}  # rel_path_str -> file qualified_name

        for rel_path in files:
            rel_str = str(rel_path)
            abs_path = self.root_path / rel_path
            all_file_strs.add(rel_str)

            # Determine language
            language = self.registry.language_for_file(abs_path)
            if language is None:
                continue

            file_languages[rel_str] = language

            # Parse
            try:
                tree = self.registry.parse_file(abs_path)
            except Exception as exc:
                stats.errors.append(f"Parse error in {rel_str}: {exc}")
                continue

            stats.files_parsed += 1

            # Extract
            try:
                definitions = extract_definitions(tree, rel_str, language)
                imports = extract_imports(tree, rel_str, language)
                calls = extract_calls(tree, rel_str, language)
            except Exception as exc:
                stats.errors.append(f"Extraction error in {rel_str}: {exc}")
                definitions, imports, calls = [], [], []

            file_definitions[rel_str] = definitions
            file_imports[rel_str] = imports
            file_calls[rel_str] = calls

            # Build module path (both stripped and full variants for resolution)
            module_path = _module_path_for_file(rel_path, language)
            module_to_file[module_path] = rel_str
            full_module_path = _module_path_for_file_full(rel_path, language)
            if full_module_path != module_path:
                module_to_file[full_module_path] = rel_str

            # Content hash
            content_hash = compute_file_hash(abs_path)

            # Read file source for definition-level content hashing
            try:
                source_lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines(
                    True
                )
            except Exception:
                source_lines = []

            # File node
            file_qname = f"file::{rel_str}"
            file_qnames[rel_str] = file_qname
            all_nodes.append(
                {
                    "kind": "file",
                    "name": rel_path.name,
                    "qualified_name": file_qname,
                    "file_path": rel_str,
                    "start_line": None,
                    "end_line": None,
                    "language": language,
                    "content_hash": content_hash,
                    "graph_version": graph_version,
                }
            )

            # Definition nodes
            for defn in definitions:
                # Build full qualified name: module_path::ClassName::method or module_path::func
                if "." in defn.qualified_name:
                    # e.g. "ClassName.method_name" -> "module::ClassName::method_name"
                    parts = defn.qualified_name.split(".")
                    qname = f"{module_path}::{'::'.join(parts)}"
                else:
                    qname = f"{module_path}::{defn.qualified_name}"

                # Compute definition-level content hash from source lines.
                def_hash = None
                if source_lines and defn.start_line and defn.end_line:
                    start = max(0, defn.start_line - 1)
                    end = min(len(source_lines), defn.end_line)
                    snippet = "".join(source_lines[start:end])
                    def_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

                all_nodes.append(
                    {
                        "kind": defn.kind,
                        "name": defn.name,
                        "qualified_name": qname,
                        "file_path": rel_str,
                        "start_line": defn.start_line,
                        "end_line": defn.end_line,
                        "language": defn.language,
                        "content_hash": def_hash,
                        "graph_version": graph_version,
                    }
                )

                all_contains_edges.append((file_qname, qname))

                # Track name for call resolution
                name_to_defs.setdefault(defn.name, []).append((qname, rel_str))

        # Upsert all nodes
        if all_nodes:
            ids = self.graph_store.upsert_nodes(all_nodes)
            stats.nodes_created += len(ids)

            # Build lookup from qualified_name -> id
            for node_dict, node_id in zip(all_nodes, ids, strict=True):
                qname = node_dict["qualified_name"]
                if node_dict["kind"] == "file":
                    file_node_ids[node_dict["file_path"]] = node_id
                else:
                    def_node_ids[qname] = node_id

        # Create contains edges
        contains_edges: list[dict[str, Any]] = []
        for file_qname, def_qname in all_contains_edges:
            # Look up IDs -- file node id
            # Find file_path from file_qname
            src_id = None
            tgt_id = def_node_ids.get(def_qname)
            for fp, fqn in file_qnames.items():
                if fqn == file_qname:
                    src_id = file_node_ids.get(fp)
                    break
            if src_id is not None and tgt_id is not None:
                contains_edges.append(
                    {
                        "source_id": src_id,
                        "target_id": tgt_id,
                        "kind": "contains",
                        "properties": {"confidence": "high"},
                    }
                )

        if contains_edges:
            self.graph_store.upsert_edges(contains_edges)
            stats.edges_created += len(contains_edges)

        # -- Phase 2: Cross-file resolution --
        import_edges: list[dict[str, Any]] = []
        # Track what names are imported into each file: {file: {local_name: (target_file, imported_name)}}
        import_name_map: dict[str, dict[str, tuple[str, str]]] = {}

        for rel_str, imports in file_imports.items():
            language = file_languages.get(rel_str, "python")

            for imp in imports:
                target_file: str | None = None

                if language == "python":
                    target_file = _resolve_python_import_to_file(imp, module_to_file)
                elif language in ("typescript", "tsx", "javascript"):
                    target_file = _resolve_ts_import_to_file(imp, rel_str, all_file_strs)

                if target_file is None:
                    continue

                # Create import edge between file nodes
                src_id = file_node_ids.get(rel_str)
                tgt_id = file_node_ids.get(target_file)
                if src_id is not None and tgt_id is not None:
                    import_edges.append(
                        {
                            "source_id": src_id,
                            "target_id": tgt_id,
                            "kind": "imports",
                            "properties": {"confidence": "high"},
                        }
                    )

                # Track imported names for call resolution
                if rel_str not in import_name_map:
                    import_name_map[rel_str] = {}
                for name in imp.imported_names:
                    import_name_map[rel_str][name] = (target_file, name)

        if import_edges:
            self.graph_store.upsert_edges(import_edges)
            stats.edges_created += len(import_edges)

        # -- Phase 3: Call resolution --
        call_edges: list[dict[str, Any]] = []

        for rel_str, calls in file_calls.items():
            language = file_languages.get(rel_str, "python")
            imports_map = import_name_map.get(rel_str, {})

            for call in calls:
                target_qname: str | None = None
                confidence = "medium"

                # Case 1: self.method() -- resolve within same class
                if call.qualifier == "self" or call.qualifier == "this":
                    enclosing = call.enclosing_scope
                    if enclosing:
                        # Find the class that contains this scope
                        module_path_str = _module_path_for_file(Path(rel_str), language)
                        # Try enclosing scope as class name
                        candidate = f"{module_path_str}::{enclosing}::{call.callee_name}"
                        if candidate in def_node_ids:
                            target_qname = candidate
                            confidence = "high"
                        else:
                            # The enclosing_scope might be the method, so look for the class
                            for defn in file_definitions.get(rel_str, []):
                                if defn.kind == "class":
                                    candidate = (
                                        f"{module_path_str}::{defn.name}::{call.callee_name}"
                                    )
                                    if candidate in def_node_ids:
                                        target_qname = candidate
                                        confidence = "medium"
                                        break

                # Case 2: imported name call
                elif call.qualifier is None and call.callee_name in imports_map:
                    target_file, imported_name = imports_map[call.callee_name]
                    # Find the definition in the target file
                    candidates = name_to_defs.get(imported_name, [])
                    for qname, fpath in candidates:
                        if fpath == target_file:
                            target_qname = qname
                            confidence = "medium"
                            break

                # Case 3: qualified call on imported name (e.g. service.add_user())
                elif call.qualifier is not None and call.qualifier in imports_map:
                    target_file, imported_name = imports_map[call.qualifier]
                    # The qualifier is a class/object; look for method
                    candidates = name_to_defs.get(imported_name, [])
                    for qname, fpath in candidates:
                        if fpath == target_file:
                            # Found the class; now look for the method
                            method_qname = f"{qname}::{call.callee_name}"
                            if method_qname in def_node_ids:
                                target_qname = method_qname
                                confidence = "medium"
                            break

                # Case 4: local function call
                elif call.qualifier is None:
                    module_path_str = _module_path_for_file(Path(rel_str), language)
                    candidate = f"{module_path_str}::{call.callee_name}"
                    if candidate in def_node_ids:
                        target_qname = candidate
                        confidence = "medium"

                if target_qname is not None:
                    # Find the caller's enclosing definition node
                    caller_qname: str | None = None
                    if call.enclosing_scope:
                        module_path_str = _module_path_for_file(Path(rel_str), language)
                        # Try as top-level function
                        candidate = f"{module_path_str}::{call.enclosing_scope}"
                        if candidate in def_node_ids:
                            caller_qname = candidate
                        else:
                            # Try as method within each class in the file
                            for defn in file_definitions.get(rel_str, []):
                                if defn.kind == "class":
                                    candidate = (
                                        f"{module_path_str}::{defn.name}::{call.enclosing_scope}"
                                    )
                                    if candidate in def_node_ids:
                                        caller_qname = candidate
                                        break

                    # Fall back to file node as caller
                    src_id = (
                        def_node_ids.get(caller_qname)
                        if caller_qname
                        else file_node_ids.get(rel_str)
                    )
                    tgt_id = def_node_ids.get(target_qname)

                    if src_id is not None and tgt_id is not None:
                        call_edges.append(
                            {
                                "source_id": src_id,
                                "target_id": tgt_id,
                                "kind": "calls",
                                "properties": {"confidence": confidence},
                            }
                        )

        if call_edges:
            self.graph_store.upsert_edges(call_edges)
            stats.edges_created += len(call_edges)
