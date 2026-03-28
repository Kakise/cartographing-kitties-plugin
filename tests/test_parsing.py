"""Tests for the cartograph.parsing module."""

from pathlib import Path

import pytest

from cartograph.parsing import (
    ParserRegistry,
    extract_calls,
    extract_definitions,
    extract_imports,
)


@pytest.fixture
def registry() -> ParserRegistry:
    return ParserRegistry()


# ---------------------------------------------------------------------------
# Test 1: Parse a Python file with functions, classes, imports, and calls
# ---------------------------------------------------------------------------


class TestPythonExtraction:
    def test_definitions(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        defs = extract_definitions(tree, sample_python_file, "python")

        names = {d.name for d in defs}
        assert "MyClass" in names
        assert "__init__" in names
        assert "greet" in names
        assert "helper_function" in names
        assert "main" in names

        # Check kinds
        kinds = {d.name: d.kind for d in defs}
        assert kinds["MyClass"] == "class"
        assert kinds["helper_function"] == "function"
        assert kinds["main"] == "function"
        assert kinds["__init__"] == "method"
        assert kinds["greet"] == "method"

    def test_qualified_names(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        defs = extract_definitions(tree, sample_python_file, "python")
        qualified = {d.name: d.qualified_name for d in defs}
        assert qualified["__init__"] == "MyClass.__init__"
        assert qualified["greet"] == "MyClass.greet"
        assert qualified["helper_function"] == "helper_function"

    def test_imports(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        imports = extract_imports(tree, sample_python_file, "python")

        assert len(imports) == 2
        mod_paths = {i.module_path for i in imports}
        assert "os" in mod_paths
        assert "pathlib" in mod_paths

        pathlib_imp = [i for i in imports if i.module_path == "pathlib"][0]
        assert "Path" in pathlib_imp.imported_names
        assert pathlib_imp.is_relative is False

    def test_calls(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        calls = extract_calls(tree, sample_python_file, "python")

        callee_names = [c.callee_name for c in calls]
        assert "MyClass" in callee_names
        assert "print" in callee_names
        assert "greet" in callee_names
        assert "helper_function" in callee_names
        assert "join" in callee_names

    def test_call_qualifiers(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        calls = extract_calls(tree, sample_python_file, "python")

        greet_call = [c for c in calls if c.callee_name == "greet"][0]
        assert greet_call.qualifier == "obj"

        join_call = [c for c in calls if c.callee_name == "join"][0]
        assert join_call.qualifier == "os.path"

    def test_call_enclosing_scope(self, registry: ParserRegistry, sample_python_file: Path):
        tree = registry.parse_file(sample_python_file)
        calls = extract_calls(tree, sample_python_file, "python")

        myclass_call = [c for c in calls if c.callee_name == "MyClass"][0]
        assert myclass_call.enclosing_scope == "main"


# ---------------------------------------------------------------------------
# Test 2: Parse a TypeScript file with interfaces, types, enums, and imports
# ---------------------------------------------------------------------------


class TestTypeScriptExtraction:
    def test_definitions(self, registry: ParserRegistry, sample_typescript_file: Path):
        tree = registry.parse_file(sample_typescript_file)
        defs = extract_definitions(tree, sample_typescript_file, "typescript")

        names = {d.name for d in defs}
        assert "User" in names  # interface
        assert "UserID" in names  # type alias
        assert "Role" in names  # enum
        assert "UserService" in names  # class
        assert "getUser" in names  # method
        assert "addUser" in names  # method
        assert "createUser" in names  # arrow function

    def test_definition_kinds(self, registry: ParserRegistry, sample_typescript_file: Path):
        tree = registry.parse_file(sample_typescript_file)
        defs = extract_definitions(tree, sample_typescript_file, "typescript")
        kinds = {d.name: d.kind for d in defs}

        assert kinds["User"] == "interface"
        assert kinds["UserID"] == "type_alias"
        assert kinds["Role"] == "enum"
        assert kinds["UserService"] == "class"
        assert kinds["getUser"] == "method"
        assert kinds["addUser"] == "method"
        assert kinds["createUser"] == "function"

    def test_method_qualified_names(self, registry: ParserRegistry, sample_typescript_file: Path):
        tree = registry.parse_file(sample_typescript_file)
        defs = extract_definitions(tree, sample_typescript_file, "typescript")
        qualified = {d.name: d.qualified_name for d in defs}

        assert qualified["getUser"] == "UserService.getUser"
        assert qualified["addUser"] == "UserService.addUser"

    def test_imports(self, registry: ParserRegistry, sample_typescript_file: Path):
        tree = registry.parse_file(sample_typescript_file)
        imports = extract_imports(tree, sample_typescript_file, "typescript")

        assert len(imports) == 1
        imp = imports[0]
        assert imp.module_path == "fs/promises"
        assert "readFile" in imp.imported_names
        assert imp.is_relative is False

    def test_calls(self, registry: ParserRegistry, sample_typescript_file: Path):
        tree = registry.parse_file(sample_typescript_file)
        calls = extract_calls(tree, sample_typescript_file, "typescript")

        callee_names = [c.callee_name for c in calls]
        # this.users.get(id), this.users.set(...)
        assert "get" in callee_names
        assert "set" in callee_names
        # new Map()
        assert "Map" in callee_names


# ---------------------------------------------------------------------------
# Test 3: Relative imports
# ---------------------------------------------------------------------------


class TestRelativeImports:
    def test_python_relative_imports(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "rel.py"
        f.write_text(
            "from . import utils\nfrom ..base import Base\nfrom ...deep.module import thing\n"
        )
        tree = registry.parse_file(f)
        imports = extract_imports(tree, f, "python")

        assert len(imports) == 3

        imp_utils = imports[0]
        assert imp_utils.is_relative is True
        assert imp_utils.module_path == "."
        assert "utils" in imp_utils.imported_names

        imp_base = imports[1]
        assert imp_base.is_relative is True
        assert imp_base.module_path == "..base"
        assert "Base" in imp_base.imported_names

        imp_deep = imports[2]
        assert imp_deep.is_relative is True
        assert imp_deep.module_path == "...deep.module"
        assert "thing" in imp_deep.imported_names

    def test_ts_relative_imports(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "rel.ts"
        f.write_text('import { foo } from "./utils";\nimport { bar } from "../base";\n')
        tree = registry.parse_file(f)
        imports = extract_imports(tree, f, "typescript")

        assert len(imports) == 2
        assert imports[0].module_path == "./utils"
        assert imports[0].is_relative is True
        assert imports[1].module_path == "../base"
        assert imports[1].is_relative is True


# ---------------------------------------------------------------------------
# Test 4: Decorated Python functions
# ---------------------------------------------------------------------------


class TestDecoratedDefinitions:
    def test_decorated_function_found(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "deco.py"
        f.write_text(
            "@my_decorator\n"
            "def decorated_func():\n"
            "    pass\n"
            "\n"
            "@app.route('/')\n"
            "def handler():\n"
            "    pass\n"
        )
        tree = registry.parse_file(f)
        defs = extract_definitions(tree, f, "python")

        names = {d.name for d in defs}
        assert "decorated_func" in names
        assert "handler" in names
        assert all(d.kind == "function" for d in defs)

    def test_decorated_class_found(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "deco_class.py"
        f.write_text("@dataclass\nclass MyData:\n    x: int\n    y: str\n")
        tree = registry.parse_file(f)
        defs = extract_definitions(tree, f, "python")

        assert len(defs) == 1
        assert defs[0].name == "MyData"
        assert defs[0].kind == "class"


# ---------------------------------------------------------------------------
# Test 5: Arrow functions assigned to const in TypeScript
# ---------------------------------------------------------------------------


class TestArrowFunctions:
    def test_arrow_function_captured(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "arrow.ts"
        f.write_text(
            "const add = (a: number, b: number): number => a + b;\n"
            "const greet = (name: string): string => {\n"
            "    return `Hello, ${name}`;\n"
            "};\n"
            "let notArrow = 42;\n"
        )
        tree = registry.parse_file(f)
        defs = extract_definitions(tree, f, "typescript")

        names = {d.name for d in defs}
        assert "add" in names
        assert "greet" in names
        assert "notArrow" not in names

        for d in defs:
            assert d.kind == "function"

    def test_js_arrow_function(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "arrow.js"
        f.write_text("const square = (x) => x * x;\n")
        tree = registry.parse_file(f)
        defs = extract_definitions(tree, f, "javascript")

        assert len(defs) == 1
        assert defs[0].name == "square"
        assert defs[0].kind == "function"
        assert defs[0].language == "javascript"


# ---------------------------------------------------------------------------
# Test 6: Empty file returns empty results
# ---------------------------------------------------------------------------


class TestEmptyFile:
    def test_empty_python(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "empty.py"
        f.write_text("")
        tree = registry.parse_file(f)

        assert extract_definitions(tree, f, "python") == []
        assert extract_imports(tree, f, "python") == []
        assert extract_calls(tree, f, "python") == []

    def test_empty_typescript(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "empty.ts"
        f.write_text("")
        tree = registry.parse_file(f)

        assert extract_definitions(tree, f, "typescript") == []
        assert extract_imports(tree, f, "typescript") == []
        assert extract_calls(tree, f, "typescript") == []


# ---------------------------------------------------------------------------
# Test 7: File with syntax errors -- graceful handling
# ---------------------------------------------------------------------------


class TestSyntaxErrors:
    def test_partial_python_parse(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "broken.py"
        f.write_text(
            "def valid_func():\n"
            "    pass\n"
            "\n"
            "def broken_func(\n"  # Missing closing paren
            "\n"
            "class StillValid:\n"
            "    pass\n"
        )
        tree = registry.parse_file(f)
        # tree-sitter produces partial tree; root has errors
        assert tree.root_node.has_error

        defs = extract_definitions(tree, f, "python")
        names = {d.name for d in defs}
        # The valid definitions should still be extracted
        assert "valid_func" in names

    def test_partial_ts_parse(self, registry: ParserRegistry, tmp_project: Path):
        f = tmp_project / "broken.ts"
        f.write_text(
            "interface Valid {\n"
            "    name: string;\n"
            "}\n"
            "\n"
            "const broken = (\n"  # Incomplete
            "\n"
            "enum StillValid {\n"
            "    A = 1\n"
            "}\n"
        )
        tree = registry.parse_file(f)
        assert tree.root_node.has_error

        defs = extract_definitions(tree, f, "typescript")
        names = {d.name for d in defs}
        assert "Valid" in names


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestParserRegistry:
    def test_get_parser_python(self, registry: ParserRegistry, tmp_project: Path):
        parser, lang = registry.get_parser("test.py")
        assert parser is not None
        assert lang is not None

    def test_get_parser_typescript(self, registry: ParserRegistry):
        parser, lang = registry.get_parser("test.ts")
        assert parser is not None

    def test_get_parser_tsx(self, registry: ParserRegistry):
        parser, lang = registry.get_parser("test.tsx")
        assert parser is not None

    def test_get_parser_javascript(self, registry: ParserRegistry):
        parser, lang = registry.get_parser("test.js")
        assert parser is not None

    def test_get_parser_jsx(self, registry: ParserRegistry):
        parser, lang = registry.get_parser("test.jsx")
        assert parser is not None

    def test_unsupported_extension(self, registry: ParserRegistry):
        with pytest.raises(ValueError, match="Unsupported file extension"):
            registry.get_parser("test.rs")

    def test_parser_caching(self, registry: ParserRegistry):
        p1, l1 = registry.get_parser("a.py")
        p2, l2 = registry.get_parser("b.py")
        assert p1 is p2
        assert l1 is l2

    def test_language_for_file(self):
        assert ParserRegistry.language_for_file("test.py") == "python"
        assert ParserRegistry.language_for_file("test.ts") == "typescript"
        assert ParserRegistry.language_for_file("test.tsx") == "tsx"
        assert ParserRegistry.language_for_file("test.js") == "javascript"
        assert ParserRegistry.language_for_file("test.jsx") == "javascript"
        assert ParserRegistry.language_for_file("test.rs") is None
