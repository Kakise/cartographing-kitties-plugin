"""Per-language S-expression query sets for tree-sitter extraction.

NOTE: In tree-sitter 0.25+, the Query object no longer exposes matches/captures
methods directly. We store the query strings here for reference and potential
future use, but the actual extraction uses manual tree walking in extractors.py.
"""

from __future__ import annotations

# Query strings keyed by language -> query type -> S-expression.
# These document the node types we care about per language.
QUERIES: dict[str, dict[str, str]] = {
    "python": {
        "definitions": """
            [
                (function_definition
                    name: (identifier) @def.name) @def.node
                (class_definition
                    name: (identifier) @class.name) @class.node
                (decorated_definition) @decorated.node
            ]
        """,
        "imports": """
            [
                (import_statement) @import.node
                (import_from_statement) @import_from.node
            ]
        """,
        "calls": """
            (call
                function: [
                    (identifier) @call.name
                    (attribute) @call.attr
                ]) @call.node
        """,
    },
    "typescript": {
        "definitions": """
            [
                (function_declaration
                    name: (identifier) @def.name) @def.node
                (class_declaration
                    name: (type_identifier) @class.name) @class.node
                (interface_declaration
                    name: (type_identifier) @iface.name) @iface.node
                (type_alias_declaration
                    name: (type_identifier) @type.name) @type.node
                (enum_declaration
                    name: (identifier) @enum.name) @enum.node
                (method_definition
                    name: (property_identifier) @method.name) @method.node
                (lexical_declaration
                    (variable_declarator
                        name: (identifier) @var.name
                        value: (arrow_function))) @arrow.node
            ]
        """,
        "imports": """
            (import_statement) @import.node
        """,
        "calls": """
            [
                (call_expression) @call.node
                (new_expression) @new.node
            ]
        """,
    },
    "javascript": {
        "definitions": """
            [
                (function_declaration
                    name: (identifier) @def.name) @def.node
                (class_declaration
                    name: (identifier) @class.name) @class.node
                (method_definition
                    name: (property_identifier) @method.name) @method.node
                (lexical_declaration
                    (variable_declarator
                        name: (identifier) @var.name
                        value: (arrow_function))) @arrow.node
            ]
        """,
        "imports": """
            (import_statement) @import.node
        """,
        "calls": """
            [
                (call_expression) @call.node
                (new_expression) @new.node
            ]
        """,
    },
}

# TSX shares TypeScript queries
QUERIES["tsx"] = QUERIES["typescript"]

# Node type sets used by extractors for tree walking
PYTHON_DEF_TYPES = {"function_definition", "class_definition", "decorated_definition"}
PYTHON_IMPORT_TYPES = {"import_statement", "import_from_statement"}
PYTHON_CALL_TYPES = {"call"}

TS_DEF_TYPES = {
    "function_declaration",
    "class_declaration",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
    "method_definition",
    "lexical_declaration",
}
TS_IMPORT_TYPES = {"import_statement"}
TS_CALL_TYPES = {"call_expression", "new_expression"}
TS_EXPORT_TYPES = {"export_statement"}
