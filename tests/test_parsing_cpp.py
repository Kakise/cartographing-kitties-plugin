"""Tests for the C++ extractor."""

from pathlib import Path

import pytest

from cartograph.parsing import (
    ParserRegistry,
    extract_calls,
    extract_definitions,
    extract_imports,
    extract_inheritance,
)


@pytest.fixture
def registry() -> ParserRegistry:
    return ParserRegistry()


@pytest.fixture
def cpp_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.cpp"
    f.write_text(
        """\
#include "shape.h"
#include <vector>

class Shape {
public:
    virtual double area() const = 0;
};

class Circle : public Shape {
public:
    double radius;
    Circle(double r);
    double area() const override;
};

namespace geo {
class Triangle {
public:
    double area() const { return 0.0; }
};

void free_in_ns() {}
}

double Circle::area() const {
    return 3.14 * radius * radius;
}

enum class Color { Red, Green };
using StringList = std::vector<int>;
typedef int Index;

namespace { void anon_helper() {} }

void top_level() {}
"""
    )
    return f


@pytest.fixture
def c_style_header(tmp_path: Path) -> Path:
    """A pure-C header with no C++ constructs — must parse without errors."""
    f = tmp_path / "legacy.h"
    f.write_text(
        """\
#ifndef LEGACY_H
#define LEGACY_H
struct Point { int x; int y; };
int distance(struct Point a, struct Point b);
#endif
"""
    )
    return f


class TestCppDefinitions:
    def test_classes(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        classes = {d.name: d.qualified_name for d in defs if d.kind == "class"}
        assert "Shape" in classes
        assert "Circle" in classes
        # Triangle is namespaced inside `geo`
        assert classes["Triangle"] == "geo.Triangle"

    def test_inline_method_method_kind(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        triangle_area = [d for d in defs if d.qualified_name == "geo.Triangle.area"]
        assert triangle_area
        assert triangle_area[0].kind == "method"

    def test_out_of_line_method(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        # `double Circle::area() const { ... }` produces Circle.area
        circle_area = [d for d in defs if d.qualified_name == "Circle.area"]
        assert circle_area
        assert circle_area[0].kind == "method"

    def test_pure_virtual_method_recorded(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        shape_area = [d for d in defs if d.qualified_name == "Shape.area"]
        assert shape_area
        assert shape_area[0].kind == "method"

    def test_namespaces_as_modules(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        ns = [d for d in defs if d.kind == "module"]
        names = {d.name for d in ns}
        assert "geo" in names

    def test_anonymous_namespace_skipped(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        # No module node should be produced from the anonymous namespace.
        # The helper inside it should still appear (as a free function).
        helpers = [d for d in defs if d.name == "anon_helper"]
        assert helpers
        assert helpers[0].kind == "function"
        # No `module` node ends with `anon_helper`
        modules = [d for d in defs if d.kind == "module"]
        assert all(d.name != "" for d in modules)

    def test_enum_and_type_aliases(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        kinds = {d.name: d.kind for d in defs}
        assert kinds["Color"] == "enum"
        assert kinds["StringList"] == "type_alias"
        assert kinds["Index"] == "type_alias"

    def test_free_function(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        defs = extract_definitions(tree, cpp_file, "cpp")
        top_level = [d for d in defs if d.name == "top_level"]
        assert top_level
        assert top_level[0].kind == "function"


class TestCppImports:
    def test_quoted_include_is_relative(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        imports = extract_imports(tree, cpp_file, "cpp")
        quoted = [i for i in imports if i.module_path == "shape.h"]
        assert quoted
        assert quoted[0].is_relative is True

    def test_angle_include_is_external(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        imports = extract_imports(tree, cpp_file, "cpp")
        sys_inc = [i for i in imports if i.module_path == "vector"]
        assert sys_inc
        assert sys_inc[0].is_relative is False


class TestCppCalls:
    def test_field_call(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        # We need a fixture with actual call sites — re-test using a tiny inline one
        path = cpp_file.parent / "calls.cpp"
        path.write_text(
            """\
class Foo {
public:
    double area() const;
};

void run() {
    Foo f;
    f.area();
    free_func();
    ns::scoped();
}
"""
        )
        tree2 = registry.parse_file(path)
        calls = extract_calls(tree2, path, "cpp")
        names = {c.callee_name for c in calls}
        assert {"area", "free_func", "scoped"}.issubset(names)
        # f.area() — qualifier should be 'f'
        area_call = [c for c in calls if c.callee_name == "area"][0]
        assert area_call.qualifier == "f"


class TestCppInheritance:
    def test_class_inherits_base(self, registry: ParserRegistry, cpp_file: Path):
        tree = registry.parse_file(cpp_file)
        inh = extract_inheritance(tree, cpp_file, "cpp")
        pairs = {(i.child_qname, i.parent_name) for i in inh}
        assert ("Circle", "Shape") in pairs


class TestCppCStyleHeader:
    def test_c_header_parses_without_error(self, registry: ParserRegistry, c_style_header: Path):
        tree = registry.parse_file(c_style_header)
        assert not tree.root_node.has_error
        defs = extract_definitions(tree, c_style_header, "cpp")
        # The struct should be picked up as a class
        names = {d.name for d in defs}
        assert "Point" in names
