"""Extract definitions, imports, and call sites from tree-sitter parse trees.

Uses manual tree walking rather than S-expression queries because tree-sitter
0.25+ Query objects don't expose matches/captures methods in the Python binding.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node, Tree

from .queries import (
    CPP_CALL_TYPES,
    CPP_IMPORT_TYPES,
    PYTHON_CALL_TYPES,
    PYTHON_DEF_TYPES,
    PYTHON_IMPORT_TYPES,
    RUST_CALL_TYPES,
    RUST_DEF_TYPES,
    RUST_IMPORT_TYPES,
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


@dataclass
class Inheritance:
    """A `child inherits parent` relationship (Rust `impl Trait for Type`, C++ `class D : B`)."""

    child_qname: str  # local qualified name, e.g. "Circle" or "geo::Triangle"
    parent_name: str  # unqualified name to resolve, e.g. "Shape"
    file_path: str
    language: str


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
# Rust helpers
# ---------------------------------------------------------------------------


def _rust_type_name(node: Node | None) -> str:
    """Return the type identifier name, unwrapping generic_type wrappers."""
    if node is None:
        return ""
    if node.type in ("type_identifier", "identifier"):
        return _node_text(node)
    if node.type == "generic_type":
        inner = node.child_by_field_name("type")
        return _rust_type_name(inner) if inner else _node_text(node)
    return _node_text(node)


def _find_enclosing_rust_impl_type(node: Node) -> str | None:
    """Walk parents to find the enclosing impl_item's type."""
    current = node.parent
    while current is not None:
        if current.type == "impl_item":
            type_node = current.child_by_field_name("type")
            return _rust_type_name(type_node)
        current = current.parent
    return None


def _find_enclosing_rust_trait_name(node: Node) -> str | None:
    """Walk parents to find the enclosing trait_item's name."""
    current = node.parent
    while current is not None:
        if current.type == "trait_item":
            name_node = current.child_by_field_name("name")
            return _node_text(name_node) if name_node else None
        current = current.parent
    return None


def _build_rust_path(node: Node | None) -> str:
    """Convert a Rust path node (scoped_identifier/identifier/crate/self/super) to dot-path."""
    if node is None:
        return ""
    t = node.type
    if t in ("identifier", "type_identifier"):
        return _node_text(node)
    if t in ("crate", "self", "super"):
        return t
    if t == "scoped_identifier":
        path = _build_rust_path(node.child_by_field_name("path"))
        name_node = node.child_by_field_name("name")
        name = _node_text(name_node) if name_node else ""
        if path and name:
            return f"{path}.{name}"
        return path or name
    return _node_text(node)


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
# Rust extractors
# ---------------------------------------------------------------------------


def _extract_rust_definitions(root: Node, file_path: str) -> list[Definition]:
    defs: list[Definition] = []
    nodes = _walk_tree(root, RUST_DEF_TYPES)

    for node in nodes:
        if node.type == "function_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            impl_type = _find_enclosing_rust_impl_type(node)
            if impl_type:
                qualified = f"{impl_type}.{name}"
                kind = "method"
            else:
                qualified = name
                kind = "function"
            defs.append(
                Definition(
                    name=name,
                    kind=kind,
                    qualified_name=qualified,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

        elif node.type == "function_signature_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            trait_name = _find_enclosing_rust_trait_name(node)
            if trait_name:
                qualified = f"{trait_name}.{name}"
                kind = "method"
            else:
                qualified = name
                kind = "function"
            defs.append(
                Definition(
                    name=name,
                    kind=kind,
                    qualified_name=qualified,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

        elif node.type == "struct_item":
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
                    language="rust",
                )
            )

        elif node.type == "enum_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            defs.append(
                Definition(
                    name=name,
                    kind="enum",
                    qualified_name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

        elif node.type == "trait_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            defs.append(
                Definition(
                    name=name,
                    kind="interface",
                    qualified_name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

        elif node.type == "type_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            defs.append(
                Definition(
                    name=name,
                    kind="type_alias",
                    qualified_name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

        elif node.type == "mod_item":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue
            name = _node_text(name_node)
            defs.append(
                Definition(
                    name=name,
                    kind="module",
                    qualified_name=name,
                    file_path=file_path,
                    start_line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    language="rust",
                )
            )

    return defs


def _parse_rust_use_argument(
    argument: Node, source_file: str, accumulated_prefix: str = ""
) -> list[Import]:
    """Convert a use-declaration argument subtree into Import records.

    Handles scoped_identifier (single), scoped_use_list (multiple), use_as_clause
    (aliased), use_wildcard (glob), and bare identifier forms.
    """
    results: list[Import] = []
    t = argument.type

    def is_relative_path(p: str) -> bool:
        return p.startswith("self") or p.startswith("super")

    def join_prefix(prefix: str, tail: str) -> str:
        if prefix and tail:
            return f"{prefix}.{tail}"
        return prefix or tail

    if t == "scoped_identifier":
        path = _build_rust_path(argument.child_by_field_name("path"))
        name_node = argument.child_by_field_name("name")
        leaf = _node_text(name_node) if name_node else ""
        full_path = join_prefix(accumulated_prefix, path)
        results.append(
            Import(
                module_path=full_path,
                imported_names=[leaf] if leaf else [],
                alias=None,
                is_relative=is_relative_path(full_path),
                source_file=source_file,
            )
        )

    elif t == "scoped_use_list":
        path_node = argument.child_by_field_name("path")
        list_node = argument.child_by_field_name("list")
        path = _build_rust_path(path_node)
        full_path = join_prefix(accumulated_prefix, path)
        names: list[str] = []
        if list_node is not None:
            for child in list_node.children:
                if child.type == "identifier":
                    names.append(_node_text(child))
                elif child.type == "scoped_identifier":
                    # Nested: use a::{b::c} — recurse with extended prefix
                    results.extend(_parse_rust_use_argument(child, source_file, full_path))
                elif child.type == "self":
                    # `use a::{self}` imports the module a itself
                    names.append("self")
                elif child.type == "use_as_clause":
                    results.extend(_parse_rust_use_argument(child, source_file, full_path))
        if names:
            results.append(
                Import(
                    module_path=full_path,
                    imported_names=names,
                    alias=None,
                    is_relative=is_relative_path(full_path),
                    source_file=source_file,
                )
            )

    elif t == "use_as_clause":
        path_node = argument.child_by_field_name("path")
        alias_node = argument.child_by_field_name("alias")
        alias_name = _node_text(alias_node) if alias_node else None
        if path_node is not None:
            if path_node.type == "scoped_identifier":
                inner_path = _build_rust_path(path_node.child_by_field_name("path"))
                inner_name_node = path_node.child_by_field_name("name")
                leaf = _node_text(inner_name_node) if inner_name_node else ""
                full_path = join_prefix(accumulated_prefix, inner_path)
                results.append(
                    Import(
                        module_path=full_path,
                        imported_names=[leaf] if leaf else [],
                        alias=alias_name,
                        is_relative=is_relative_path(full_path),
                        source_file=source_file,
                    )
                )
            elif path_node.type in ("identifier", "type_identifier"):
                leaf = _node_text(path_node)
                results.append(
                    Import(
                        module_path=accumulated_prefix,
                        imported_names=[leaf] if leaf else [],
                        alias=alias_name,
                        is_relative=is_relative_path(accumulated_prefix),
                        source_file=source_file,
                    )
                )

    elif t == "use_wildcard":
        # `use a::b::*;` — the path is the first named child (scoped_identifier)
        path_node = None
        for child in argument.children:
            if child.is_named:
                path_node = child
                break
        path = _build_rust_path(path_node) if path_node else ""
        full_path = join_prefix(accumulated_prefix, path)
        results.append(
            Import(
                module_path=full_path,
                imported_names=["*"],
                alias=None,
                is_relative=is_relative_path(full_path),
                source_file=source_file,
            )
        )

    elif t in ("identifier", "type_identifier"):
        leaf = _node_text(argument)
        results.append(
            Import(
                module_path=accumulated_prefix,
                imported_names=[leaf] if leaf else [],
                alias=None,
                is_relative=is_relative_path(accumulated_prefix),
                source_file=source_file,
            )
        )

    return results


def _extract_rust_imports(root: Node, source_file: str) -> list[Import]:
    imports: list[Import] = []
    nodes = _walk_tree(root, RUST_IMPORT_TYPES)

    for node in nodes:
        argument = node.child_by_field_name("argument")
        if argument is None:
            for child in node.children:
                if child.is_named:
                    argument = child
                    break
        if argument is None:
            continue
        imports.extend(_parse_rust_use_argument(argument, source_file))

    return imports


def _rust_enclosing_scope(node: Node) -> str | None:
    """Walk parents to find the enclosing function/method name (Rust)."""
    current = node.parent
    while current is not None:
        if current.type in ("function_item", "function_signature_item"):
            name_node = current.child_by_field_name("name")
            if name_node:
                return _node_text(name_node)
        current = current.parent
    return None


def _extract_rust_calls(root: Node, file_path: str) -> list[CallSite]:
    calls: list[CallSite] = []
    nodes = _walk_tree(root, RUST_CALL_TYPES)

    for node in nodes:
        if node.type == "call_expression":
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
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )
            elif func_node.type == "field_expression":
                value_node = func_node.child_by_field_name("value")
                field_node = func_node.child_by_field_name("field")
                calls.append(
                    CallSite(
                        callee_name=_node_text(field_node) if field_node else _node_text(func_node),
                        qualifier=_node_text(value_node) if value_node else None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )
            elif func_node.type == "scoped_identifier":
                path_node = func_node.child_by_field_name("path")
                name_node = func_node.child_by_field_name("name")
                calls.append(
                    CallSite(
                        callee_name=_node_text(name_node) if name_node else _node_text(func_node),
                        qualifier=_build_rust_path(path_node) if path_node else None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )
            else:
                calls.append(
                    CallSite(
                        callee_name=_node_text(func_node),
                        qualifier=None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )

        elif node.type == "macro_invocation":
            macro_node = node.child_by_field_name("macro")
            if macro_node is None:
                continue
            if macro_node.type == "scoped_identifier":
                path_node = macro_node.child_by_field_name("path")
                name_node = macro_node.child_by_field_name("name")
                calls.append(
                    CallSite(
                        callee_name=_node_text(name_node) if name_node else _node_text(macro_node),
                        qualifier=_build_rust_path(path_node) if path_node else None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )
            else:
                calls.append(
                    CallSite(
                        callee_name=_node_text(macro_node),
                        qualifier=None,
                        file_path=file_path,
                        start_line=node.start_point[0] + 1,
                        enclosing_scope=_rust_enclosing_scope(node),
                    )
                )

    return calls


def _extract_rust_inheritance(root: Node, file_path: str) -> list[Inheritance]:
    """Extract `impl Trait for Type` blocks as Inheritance edges (child=Type, parent=Trait)."""
    results: list[Inheritance] = []
    impls = _walk_tree(root, {"impl_item"})
    for node in impls:
        trait_node = node.child_by_field_name("trait")
        if trait_node is None:
            continue
        type_node = node.child_by_field_name("type")
        child = _rust_type_name(type_node)
        parent = _rust_type_name(trait_node)
        if child and parent:
            results.append(
                Inheritance(
                    child_qname=child,
                    parent_name=parent,
                    file_path=file_path,
                    language="rust",
                )
            )
    return results


# ---------------------------------------------------------------------------
# C++ extractors
# ---------------------------------------------------------------------------


def _cpp_namespace_path(node: Node) -> str:
    """Walk ancestor namespace_definitions and return their dotted path.

    Anonymous namespaces are skipped — items inside them get file-local scope.
    """
    parts: list[str] = []
    current = node.parent
    while current is not None:
        if current.type == "namespace_definition":
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                parts.append(_node_text(name_node))
        current = current.parent
    return ".".join(reversed(parts))


def _cpp_enclosing_class(node: Node) -> str | None:
    """Walk ancestors and return the enclosing class/struct name."""
    current = node.parent
    while current is not None:
        if current.type in ("class_specifier", "struct_specifier"):
            name_node = current.child_by_field_name("name")
            if name_node is not None:
                return _node_text(name_node)
        current = current.parent
    return None


def _cpp_unwrap_declarator(node: Node | None) -> Node | None:
    """Unwrap pointer_declarator / reference_declarator until reaching the inner declarator."""
    while node is not None and node.type in (
        "pointer_declarator",
        "reference_declarator",
    ):
        node = node.child_by_field_name("declarator")
    return node


def _cpp_function_name_and_scope(declarator: Node | None) -> tuple[str | None, str | None]:
    """Given a function_declarator, return (name, class_qualifier_or_None)."""
    if declarator is None or declarator.type != "function_declarator":
        return None, None
    inner = _cpp_unwrap_declarator(declarator.child_by_field_name("declarator"))
    if inner is None:
        return None, None
    if inner.type in ("identifier", "field_identifier"):
        return _node_text(inner), None
    if inner.type == "qualified_identifier":
        scope_node = inner.child_by_field_name("scope")
        name_node = inner.child_by_field_name("name")
        scope_text = _node_text(scope_node) if scope_node else None
        # For nested scopes (a::b::Foo), keep only the immediate class name (Foo)
        if scope_text and "::" in scope_text:
            scope_text = scope_text.split("::")[-1]
        name_text = _node_text(name_node) if name_node else None
        return name_text, scope_text
    if inner.type == "destructor_name":
        return _node_text(inner), None
    if inner.type == "operator_name":
        return _node_text(inner), None
    return None, None


def _cpp_rel_qualified(ns_path: str, local: str) -> str:
    return f"{ns_path}.{local}" if ns_path else local


def _extract_cpp_definitions(root: Node, file_path: str) -> list[Definition]:
    defs: list[Definition] = []
    seen_qnames: set[str] = set()

    def _add(defn: Definition) -> None:
        if defn.qualified_name in seen_qnames:
            return
        seen_qnames.add(defn.qualified_name)
        defs.append(defn)

    # function_definition: methods (inline or out-of-line) and free functions
    for node in _walk_tree(root, {"function_definition"}):
        declarator = _cpp_unwrap_declarator(node.child_by_field_name("declarator"))
        if declarator is None or declarator.type != "function_declarator":
            continue
        name, qualifier_scope = _cpp_function_name_and_scope(declarator)
        if not name:
            continue
        enclosing_class = qualifier_scope or _cpp_enclosing_class(node)
        ns_path = _cpp_namespace_path(node)
        if enclosing_class:
            local = f"{enclosing_class}.{name}"
            kind = "method"
        else:
            local = name
            kind = "function"
        qualified = _cpp_rel_qualified(ns_path, local)
        _add(
            Definition(
                name=name,
                kind=kind,
                qualified_name=qualified,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
            )
        )

    # class_specifier / struct_specifier + nested method declarations
    for node in _walk_tree(root, {"class_specifier", "struct_specifier"}):
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        class_name = _node_text(name_node)
        ns_path = _cpp_namespace_path(node)
        qualified = _cpp_rel_qualified(ns_path, class_name)
        _add(
            Definition(
                name=class_name,
                kind="class",
                qualified_name=qualified,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
            )
        )

        # Method declarations (no inline body): field_declaration whose declarator
        # is a function_declarator (pure-virtual or interface-style declaration).
        body = node.child_by_field_name("body")
        if body is None:
            continue
        for child in body.children:
            if child.type != "field_declaration":
                continue
            decl = _cpp_unwrap_declarator(child.child_by_field_name("declarator"))
            if decl is None or decl.type != "function_declarator":
                continue
            m_name, _ = _cpp_function_name_and_scope(decl)
            if not m_name:
                continue
            method_qualified = f"{qualified}.{m_name}"
            _add(
                Definition(
                    name=m_name,
                    kind="method",
                    qualified_name=method_qualified,
                    file_path=file_path,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    language="cpp",
                )
            )

    # namespace_definition (skip anonymous)
    for node in _walk_tree(root, {"namespace_definition"}):
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        name = _node_text(name_node)
        parent_ns = _cpp_namespace_path(node)
        qualified = _cpp_rel_qualified(parent_ns, name)
        _add(
            Definition(
                name=name,
                kind="module",
                qualified_name=qualified,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
            )
        )

    # enum_specifier (covers both plain `enum` and `enum class`)
    for node in _walk_tree(root, {"enum_specifier"}):
        name_node = node.child_by_field_name("name")
        if name_node is None:
            continue
        name = _node_text(name_node)
        ns_path = _cpp_namespace_path(node)
        qualified = _cpp_rel_qualified(ns_path, name)
        _add(
            Definition(
                name=name,
                kind="enum",
                qualified_name=qualified,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
            )
        )

    # type_definition (typedef) and alias_declaration (using X = Y)
    for node in _walk_tree(root, {"type_definition", "alias_declaration"}):
        name: str | None = None
        if node.type == "alias_declaration":
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = _node_text(name_node)
        else:  # type_definition (typedef)
            for child in reversed(node.children):
                if child.type == "type_identifier":
                    name = _node_text(child)
                    break
        if not name:
            continue
        ns_path = _cpp_namespace_path(node)
        qualified = _cpp_rel_qualified(ns_path, name)
        _add(
            Definition(
                name=name,
                kind="type_alias",
                qualified_name=qualified,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language="cpp",
            )
        )

    return defs


def _extract_cpp_imports(root: Node, source_file: str) -> list[Import]:
    """Extract `#include` directives.

    - `#include "foo.h"` → is_relative=True (resolved against source dir).
    - `#include <foo>`   → is_relative=False (leaf; never resolved to repo files).
    """
    imports: list[Import] = []
    for node in _walk_tree(root, CPP_IMPORT_TYPES):
        path_node = node.child_by_field_name("path")
        if path_node is None:
            continue
        if path_node.type == "string_literal":
            # Quoted include — extract from the string_content child
            module_path = ""
            for child in path_node.children:
                if child.type == "string_content":
                    module_path = _node_text(child)
                    break
            if not module_path:
                module_path = _node_text(path_node).strip('"')
            is_relative = True
        elif path_node.type == "system_lib_string":
            module_path = _node_text(path_node).strip("<>")
            is_relative = False
        else:
            continue
        imports.append(
            Import(
                module_path=module_path,
                imported_names=[],
                alias=None,
                is_relative=is_relative,
                source_file=source_file,
            )
        )
    return imports


def _cpp_enclosing_function_name(node: Node) -> str | None:
    current = node.parent
    while current is not None:
        if current.type == "function_definition":
            declarator = _cpp_unwrap_declarator(current.child_by_field_name("declarator"))
            name, qualifier = _cpp_function_name_and_scope(declarator)
            if name:
                return f"{qualifier}.{name}" if qualifier else name
        current = current.parent
    return None


def _extract_cpp_calls(root: Node, file_path: str) -> list[CallSite]:
    calls: list[CallSite] = []
    for node in _walk_tree(root, CPP_CALL_TYPES):
        func_node = node.child_by_field_name("function")
        if func_node is None:
            continue

        callee: str | None = None
        qualifier: str | None = None

        if func_node.type == "identifier":
            callee = _node_text(func_node)
        elif func_node.type == "field_expression":
            arg_node = func_node.child_by_field_name("argument")
            field_node = func_node.child_by_field_name("field")
            callee = _node_text(field_node) if field_node else _node_text(func_node)
            qualifier = _node_text(arg_node) if arg_node else None
        elif func_node.type == "qualified_identifier":
            scope_node = func_node.child_by_field_name("scope")
            name_node = func_node.child_by_field_name("name")
            callee = _node_text(name_node) if name_node else _node_text(func_node)
            qualifier = _node_text(scope_node) if scope_node else None
        elif func_node.type == "template_function":
            inner_name = func_node.child_by_field_name("name")
            if inner_name is not None:
                callee = _node_text(inner_name)
            else:
                callee = _node_text(func_node)
        else:
            callee = _node_text(func_node)

        if callee is None:
            continue

        calls.append(
            CallSite(
                callee_name=callee,
                qualifier=qualifier,
                file_path=file_path,
                start_line=node.start_point[0] + 1,
                enclosing_scope=_cpp_enclosing_function_name(node),
            )
        )
    return calls


def _extract_cpp_inheritance(root: Node, file_path: str) -> list[Inheritance]:
    """Extract `class D : public B` (and struct equivalents) as Inheritance records."""
    results: list[Inheritance] = []
    for node in _walk_tree(root, {"class_specifier", "struct_specifier"}):
        class_name_node = node.child_by_field_name("name")
        if class_name_node is None:
            continue
        child_name = _node_text(class_name_node)
        ns_path = _cpp_namespace_path(node)
        child_qname = _cpp_rel_qualified(ns_path, child_name)
        for child in node.children:
            if child.type != "base_class_clause":
                continue
            for grandchild in child.children:
                if grandchild.type == "type_identifier":
                    parent_name = _node_text(grandchild)
                    if parent_name:
                        results.append(
                            Inheritance(
                                child_qname=child_qname,
                                parent_name=parent_name,
                                file_path=file_path,
                                language="cpp",
                            )
                        )
                elif grandchild.type == "qualified_identifier":
                    # e.g. `class D : public ns::B` — keep the final name segment
                    name_node = grandchild.child_by_field_name("name")
                    parent_name = _node_text(name_node) if name_node else _node_text(grandchild)
                    if parent_name:
                        results.append(
                            Inheritance(
                                child_qname=child_qname,
                                parent_name=parent_name,
                                file_path=file_path,
                                language="cpp",
                            )
                        )
    return results


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
    elif language == "rust":
        return _extract_rust_definitions(root, fp)
    elif language == "cpp":
        return _extract_cpp_definitions(root, fp)
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
    elif language == "rust":
        return _extract_rust_imports(root, sf)
    elif language == "cpp":
        return _extract_cpp_imports(root, sf)
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
    elif language == "rust":
        return _extract_rust_calls(root, fp)
    elif language == "cpp":
        return _extract_cpp_calls(root, fp)
    else:
        return []


def extract_inheritance(tree: Tree, file_path: str | Path, language: str) -> list[Inheritance]:
    """Extract inheritance relationships from a parsed tree.

    Only Rust (`impl Trait for Type`) and C++ (`class D : public B`) populate this list.
    """
    fp = str(file_path)
    root = tree.root_node
    if language == "rust":
        return _extract_rust_inheritance(root, fp)
    elif language == "cpp":
        return _extract_cpp_inheritance(root, fp)
    return []
