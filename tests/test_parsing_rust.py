"""Tests for the Rust extractor."""

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
def rust_file(tmp_path: Path) -> Path:
    f = tmp_path / "sample.rs"
    f.write_text(
        """\
use crate::geometry::Circle;
use std::collections::HashMap;
use self::sibling::Foo;
use super::parent::Bar;
use std::io::{Read, Write};
use std::collections::HashMap as HM;
use crate::utils::*;

pub struct Circle {
    pub radius: f64,
}

pub enum Color {
    Red,
    Green,
}

pub type Pair = (i32, i32);

pub trait Shape {
    fn area(&self) -> f64;
}

impl Circle {
    pub fn new(radius: f64) -> Self {
        Circle { radius }
    }
}

impl Shape for Circle {
    fn area(&self) -> f64 {
        3.14 * self.radius * self.radius
    }
}

fn helper(x: i32) -> i32 {
    x + 1
}

fn generic<T: Clone>(x: T) -> T {
    x.clone()
}

fn main() {
    let c = Circle::new(1.0);
    let a = c.area();
    println!("area={}", a);
    helper(42);
}
"""
    )
    return f


class TestRustDefinitions:
    def test_struct_class_kind(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        kinds = {d.name: d.kind for d in defs}
        assert kinds["Circle"] == "class"

    def test_trait_interface_kind(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        kinds = {d.name: d.kind for d in defs}
        assert kinds["Shape"] == "interface"

    def test_enum_and_type_alias(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        kinds = {d.name: d.kind for d in defs}
        assert kinds["Color"] == "enum"
        assert kinds["Pair"] == "type_alias"

    def test_free_function(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        helper = [d for d in defs if d.name == "helper"][0]
        assert helper.kind == "function"
        assert helper.qualified_name == "helper"

    def test_impl_methods_qualified(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        # `new` and `area` are methods of Circle (across two impl blocks)
        methods = [d for d in defs if d.kind == "method" and d.name in ("new", "area")]
        qualified = {d.name: d.qualified_name for d in methods}
        assert qualified["new"] == "Circle.new"
        assert qualified["area"] == "Circle.area"
        assert all(d.kind == "method" for d in methods)

    def test_trait_method_signature(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        # The function_signature_item inside `trait Shape` becomes Shape.area
        shape_methods = [d for d in defs if d.qualified_name == "Shape.area"]
        assert len(shape_methods) == 1
        assert shape_methods[0].kind == "method"

    def test_generic_function_no_type_param_def(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        defs = extract_definitions(tree, rust_file, "rust")
        names = {d.name for d in defs}
        # `T` is a type parameter, not a definition
        assert "T" not in names
        assert "generic" in names


class TestRustImports:
    def test_simple_scoped_import(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        imports = extract_imports(tree, rust_file, "rust")
        mods = {(i.module_path, tuple(i.imported_names)) for i in imports}
        assert ("crate.geometry", ("Circle",)) in mods
        assert ("std.collections", ("HashMap",)) in mods

    def test_relative_self_super(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        imports = extract_imports(tree, rust_file, "rust")
        self_imp = [i for i in imports if i.module_path.startswith("self")]
        super_imp = [i for i in imports if i.module_path.startswith("super")]
        assert any(i.is_relative for i in self_imp)
        assert any(i.is_relative for i in super_imp)

    def test_grouped_use_list(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        imports = extract_imports(tree, rust_file, "rust")
        io_import = [i for i in imports if i.module_path == "std.io"]
        assert io_import
        names = set(io_import[0].imported_names)
        assert {"Read", "Write"}.issubset(names)

    def test_aliased_import(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        imports = extract_imports(tree, rust_file, "rust")
        aliased = [i for i in imports if i.alias == "HM"]
        assert aliased
        assert aliased[0].imported_names == ["HashMap"]

    def test_wildcard_import(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        imports = extract_imports(tree, rust_file, "rust")
        wildcards = [i for i in imports if "*" in i.imported_names]
        assert wildcards
        assert wildcards[0].module_path == "crate.utils"


class TestRustCalls:
    def test_identifier_call(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        calls = extract_calls(tree, rust_file, "rust")
        names = {c.callee_name for c in calls}
        assert "helper" in names

    def test_scoped_call(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        calls = extract_calls(tree, rust_file, "rust")
        new_calls = [c for c in calls if c.callee_name == "new"]
        assert new_calls
        assert new_calls[0].qualifier == "Circle"

    def test_field_call(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        calls = extract_calls(tree, rust_file, "rust")
        area_calls = [c for c in calls if c.callee_name == "area"]
        # `c.area()` is the user's call site; method body's `self.radius` is a
        # field access, not a call
        assert any(c.qualifier == "c" for c in area_calls)

    def test_macro_call(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        calls = extract_calls(tree, rust_file, "rust")
        names = {c.callee_name for c in calls}
        assert "println" in names


class TestRustInheritance:
    def test_impl_trait_for_type(self, registry: ParserRegistry, rust_file: Path):
        tree = registry.parse_file(rust_file)
        inh = extract_inheritance(tree, rust_file, "rust")
        pairs = {(i.child_qname, i.parent_name) for i in inh}
        assert ("Circle", "Shape") in pairs
