"""Extract definitions, imports, and call sites from tree-sitter parse trees.

Uses manual tree walking rather than S-expression queries because tree-sitter
0.25+ Query objects don't expose matches/captures methods in the Python binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node, Tree

from .queries import (
    PYTHON_CALL_TYPES,
    PYTHON_DEF_TYPES,
    PYTHON_IMPORT_TYPES,
    TS_CALL_TYPES,
    TS_DEF_TYPES,
    TS_IMPORT_TYPES,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Definition:
    name: str
    kind: str  # "function", "class", "method", "interface", "type_alias", "enum"
    qualified_name: str  # e.g. "MyClass.method_name"
    file_path: str
    start_line: int
    end_line: int
    language: str


@dataclass
class Import:
    module_path: str
    imported_names: list[str]
    alias: str | None
    is_relative: bool
    source_file: str


@dataclass
class CallSite:
    callee_name: str
    qualifier: str | None  # e.g. "self" in self.method()
    file_path: str
    start_line: int
    enclosing_scope: str | None  # name of the enclosing function/class


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_text(node: Node | None) -> str:
    """Return decoded text of a node, or empty string if None."""
    if node is None:
        return ""
    return node.text.decode("utf-8") if node.text else ""


def _find_enclosing_scope(node: Node) -> str | None:
    """Walk parents to find the enclosing function or class name."""
    current = node.parent
    while current is not None:
        if current.type in (
            "function_definition",
            "class_definition",
            "function_declaration",
            "class_declaration",
            "method_definition",
        ):
            name_node = current.child_by_field_name("name")
            if name_node:
                return _node_text(name_node)
        # For decorated_definition, look at the inner definition
        if current.type == "decorated_definition":
            for child in current.children:
                if child.type in ("function_definition", "class_definition"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        return _node_text(name_node)
        current = current.parent
    return None


def _find_enclosing_class(node: Node) -> str | None:
    """Walk parents to find the enclosing class name (skip functions)."""
    current = node.parent
    while current is not None:
        if current.type in ("class_definition", "class_declaration"):
            name_node = current.child_by_field_name("name")
            if name_node:
                return _node_text(name_node)
        if current.type == "decorated_definition":
            for child in current.children:
                if child.type in ("class_definition", "class_declaration"):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        return _node_text(name_node)
        current = current.parent
    return None


def _walk_tree(node: Node, target_types: set[str]) -> list[Node]:
    """Collect all descendant nodes whose type is in target_types."""
    results: list[Node] = []
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type in target_types:
            results.append(n)
        # Still recurse into children to find nested matches
        for child in reversed(n.children):
            stack.append(child)
    return results


# ---------------------------------------------------------------------------
# Python extractors
# ---------------------------------------------------------------------------


def _extract_python_definitions(root: Node, file_path: str) -> list[Definition]:
    defs: list[Definition] = []
    nodes = _walk_tree(root, PYTHON_DEF_TYPES)

    for node in nodes:
        if node.type == "decorated_definition":
            # Find the actual definition inside
            inner = None
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    inner = child
                    break
            if inner is None:
                continue
            name_node = inner.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            kind = "function" if inner.type == "function_definition" else "class"

            # Check if it's a method (inside a class)
            enclosing_class = _find_enclosing_class(node)
            if enclosing_class and kind == "function":
                kind = "method"
                qualified = f"{enclosing_class}.{name}"
            else:
                qualified = name

            defs.append(
                Definition(
                    name=name,
                    kind=kind,
                    qualified_name=qualified,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="python",
                )
            )

        elif node.type == "function_definition":
            # Skip if parent is a decorated_definition (already handled)
            if node.parent and node.parent.type == "decorated_definition":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            enclosing_class = _find_enclosing_class(node)
            if enclosing_class:
                kind = "method"
                qualified = f"{enclosing_class}.{name}"
            else:
                kind = "function"
                qualified = name
            defs.append(
                Definition(
                    name=name,
                    kind=kind,
                    qualified_name=qualified,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="python",
                )
            )

        elif node.type == "class_definition":
            if node.parent and node.parent.type == "decorated_definition":
                continue
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            defs.append(
                Definition(
                    name=name,
                    kind="class",
                    qualified_name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="python",
                )
            )

    return defs


def _extract_python_imports(root: Node, source_file: str) -> list[Import]:
    imports: list[Import] = []
    nodes = _walk_tree(root, PYTHON_IMPORT_TYPES)

    for node in nodes:
        if node.type == "import_statement":
            # import os / import os.path
            for child in node.children:
                if child.type == "dotted_name":
                    mod = _node_text(child)
                    imports.append(
                        Import(
                            module_path=mod,
                            imported_names=[],
                            alias=None,
                            is_relative=False,
                            source_file=source_file,
                        )
                    )
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    alias_node = child.child_by_field_name("alias")
                    mod = _node_text(name_node)
                    alias = _node_text(alias_node) if alias_node else None
                    imports.append(
                        Import(
                            module_path=mod,
                            imported_names=[],
                            alias=alias,
                            is_relative=False,
                            source_file=source_file,
                        )
                    )

        elif node.type == "import_from_statement":
            # from X import Y, Z / from . import utils / from ..base import Base
            is_relative = False
            module_path = ""
            imported_names: list[str] = []

            for child in node.children:
                if child.type == "dotted_name" and module_path == "":
                    # Module path (after 'from', before 'import')
                    module_path = _node_text(child)
                elif child.type == "relative_import":
                    is_relative = True
                    prefix_node = None
                    dotted_node = None
                    for rc in child.children:
                        if rc.type == "import_prefix":
                            prefix_node = rc
                        elif rc.type == "dotted_name":
                            dotted_node = rc
                    dots = _node_text(prefix_node) if prefix_node else ""
                    mod = _node_text(dotted_node) if dotted_node else ""
                    module_path = dots + mod
                elif child.type == "dotted_name" and module_path != "":
                    # Imported name
                    imported_names.append(_node_text(child))
                elif child.type == "aliased_import":
                    name_node = child.child_by_field_name("name")
                    imported_names.append(_node_text(name_node))

            imports.append(
                Import(
                    module_path=module_path,
                    imported_names=imported_names,
                    alias=None,
                    is_relative=is_relative,
                    source_file=source_file,
                )
            )

    return imports


def _extract_python_calls(root: Node, file_path: str) -> list[CallSite]:
    calls: list[CallSite] = []
    nodes = _walk_tree(root, PYTHON_CALL_TYPES)

    for node in nodes:
        func_node = node.child_by_field_name("function")
        if func_node is None:
            continue

        if func_node.type == "identifier":
            calls.append(
                CallSite(
                    callee_name=_node_text(func_node),
                    qualifier=None,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    enclosing_scope=_find_enclosing_scope(node),
                )
            )
        elif func_node.type == "attribute":
            # obj.method() -> qualifier=obj, callee=method
            attr_name = func_node.child_by_field_name("attribute")
            obj_node = func_node.child_by_field_name("object")
            callee = _node_text(attr_name) if attr_name else _node_text(func_node)
            qualifier = _node_text(obj_node) if obj_node else None
            calls.append(
                CallSite(
                    callee_name=callee,
                    qualifier=qualifier,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    enclosing_scope=_find_enclosing_scope(node),
                )
            )

    return calls


# ---------------------------------------------------------------------------
# TypeScript / JavaScript extractors
# ---------------------------------------------------------------------------


def _extract_ts_definitions(root: Node, file_path: str, language: str) -> list[Definition]:
    defs: list[Definition] = []
    nodes = _walk_tree(root, TS_DEF_TYPES)

    for node in nodes:
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            defs.append(
                Definition(
                    name=_node_text(name_node),
                    kind="function",
                    qualified_name=_node_text(name_node),
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            defs.append(
                Definition(
                    name=_node_text(name_node),
                    kind="class",
                    qualified_name=_node_text(name_node),
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "interface_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            defs.append(
                Definition(
                    name=_node_text(name_node),
                    kind="interface",
                    qualified_name=_node_text(name_node),
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "type_alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            defs.append(
                Definition(
                    name=_node_text(name_node),
                    kind="type_alias",
                    qualified_name=_node_text(name_node),
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "enum_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            defs.append(
                Definition(
                    name=_node_text(name_node),
                    kind="enum",
                    qualified_name=_node_text(name_node),
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            enclosing_class = _find_enclosing_class(node)
            qualified = f"{enclosing_class}.{name}" if enclosing_class else name
            defs.append(
                Definition(
                    name=name,
                    kind="method",
                    qualified_name=qualified,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language=language,
                )
            )

        elif node.type == "lexical_declaration":
            # const createUser = (...) => { ... }
            for child in node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    value_node = child.child_by_field_name("value")
                    if name_node and value_node and value_node.type == "arrow_function":
                        defs.append(
                            Definition(
                                name=_node_text(name_node),
                                kind="function",
                                qualified_name=_node_text(name_node),
                                file_path=file_path,
                                start_line=node.start_point[0] + 1,
                                end_line=node.end_point[0] + 1,
                                language=language,
                            )
                        )

    return defs


def _extract_ts_imports(root: Node, source_file: str, language: str) -> list[Import]:
    imports: list[Import] = []
    nodes = _walk_tree(root, TS_IMPORT_TYPES)

    for node in nodes:
        # Find the module string (source)
        source_node = node.child_by_field_name("source")
        if source_node is None:
            # Try to find string child directly
            for child in node.children:
                if child.type == "string":
                    source_node = child
                    break
        if source_node is None:
            continue

        # Extract module path from string node
        module_path = ""
        for child in source_node.children:
            if child.type == "string_fragment":
                module_path = _node_text(child)
                break
        if not module_path:
            # Fallback: strip quotes from string text
            raw = _node_text(source_node)
            module_path = raw.strip("'\"")

        is_relative = module_path.startswith(".")

        # Extract imported names
        imported_names: list[str] = []
        for child in node.children:
            if child.type == "import_clause":
                for clause_child in child.children:
                    if clause_child.type == "named_imports":
                        for spec in clause_child.children:
                            if spec.type == "import_specifier":
                                name_node = spec.child_by_field_name("name")
                                if name_node:
                                    imported_names.append(_node_text(name_node))
                    elif clause_child.type == "identifier":
                        # Default import
                        imported_names.append(_node_text(clause_child))
                    elif clause_child.type == "namespace_import":
                        # import * as X
                        for ns_child in clause_child.children:
                            if ns_child.type == "identifier":
                                imported_names.append(_node_text(ns_child))

        imports.append(
            Import(
                module_path=module_path,
                imported_names=imported_names,
                alias=None,
                is_relative=is_relative,
                source_file=source_file,
            )
        )

    return imports


def _extract_ts_calls(root: Node, file_path: str, language: str) -> list[CallSite]:
    calls: list[CallSite] = []
    nodes = _walk_tree(root, TS_CALL_TYPES)

    for node in nodes:
        if node.type == "new_expression":
            # new ClassName(...)
            # First named child is typically the constructor
            func_node = None
            for child in node.children:
                if child.type == "identifier" or child.type == "type_identifier":
                    func_node = child
                    break
                elif child.type == "member_expression":
                    func_node = child
                    break
            if func_node is None:
                continue
            if func_node.type == "member_expression":
                obj_node = func_node.child_by_field_name("object")
                prop_node = func_node.child_by_field_name("property")
                calls.append(
                    CallSite(
                        callee_name=_node_text(prop_node) if prop_node else _node_text(func_node),
                        qualifier=_node_text(obj_node) if obj_node else None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_find_enclosing_scope(node),
                    )
                )
            else:
                calls.append(
                    CallSite(
                        callee_name=_node_text(func_node),
                        qualifier=None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_find_enclosing_scope(node),
                    )
                )

        elif node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node is None:
                continue

            if func_node.type == "identifier":
                calls.append(
                    CallSite(
                        callee_name=_node_text(func_node),
                        qualifier=None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_find_enclosing_scope(node),
                    )
                )
            elif func_node.type == "member_expression":
                obj_node = func_node.child_by_field_name("object")
                prop_node = func_node.child_by_field_name("property")
                calls.append(
                    CallSite(
                        callee_name=_node_text(prop_node) if prop_node else _node_text(func_node),
                        qualifier=_node_text(obj_node) if obj_node else None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_find_enclosing_scope(node),
                    )
                )
            else:
                # Other callable expressions (e.g., IIFE, computed property)
                calls.append(
                    CallSite(
                        callee_name=_node_text(func_node),
                        qualifier=None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_find_enclosing_scope(node),
                    )
                )

    return calls


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_definitions(tree: Tree, file_path: str | Path, language: str) -> list[Definition]:
    """Extract all definitions from a parsed tree."""
    fp = str(file_path)
    root = tree.root_node
    if language == "python":
        return _extract_python_definitions(root, fp)
    elif language in ("typescript", "tsx", "javascript"):
        return _extract_ts_definitions(root, fp, language)
    else:
        return []


def extract_imports(tree: Tree, file_path: str | Path, language: str) -> list[Import]:
    """Extract all import statements from a parsed tree."""
    sf = str(file_path)
    root = tree.root_node
    if language == "python":
        return _extract_python_imports(root, sf)
    elif language in ("typescript", "tsx", "javascript"):
        return _extract_ts_imports(root, sf, language)
    else:
        return []


def extract_calls(tree: Tree, file_path: str | Path, language: str) -> list[CallSite]:
    """Extract all call sites from a parsed tree."""
    fp = str(file_path)
    root = tree.root_node
    if language == "python":
        return _extract_python_calls(root, fp)
    elif language in ("typescript", "tsx", "javascript"):
        return _extract_ts_calls(root, fp, language)
    else:
        return []
