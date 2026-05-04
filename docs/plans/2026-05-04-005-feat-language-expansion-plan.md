---
title: Language Expansion — Go, Rust, Java (R3)
type: feat
status: active
date: 2026-05-04
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R3
units:
  - id: 1
    title: Go extractor
    state: pending
  - id: 2
    title: Java extractor
    state: pending
  - id: 3
    title: Rust extractor
    state: pending
  - id: 4
    title: Mixed-language integration
    state: pending
  - id: 5
    title: Documentation
    state: pending
---

# Language Expansion — Implementation Plan (R3)

## Overview

Add tree-sitter-driven extraction for Go, Rust, and Java so the plugin works in polyglot 2026
stacks. Each language gets a self-contained extractor module following the existing Python and
TS/JS pattern. Schema stays fixed — every language maps onto the existing node/edge kinds. Ships
per-language (Go first, Java second, Rust third); each can merge independently.

## Problem Frame

`src/cartograph/parsing/extractors.py` has a hard-coded dispatch over `("python", "typescript",
"tsx", "javascript")`. Every other language fails at parse time. Tree-sitter grammars for Go,
Rust, and Java are mature and stable; the work is pattern-matching them to our
`Definition` / `Import` / `CallSite` dataclasses.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R3.a — Go parser, extractors, cross-file import resolution | Unit 1 |
| R3.b — Java parser, extractors, package-based import resolution | Unit 2 |
| R3.c — Rust parser, extractors, module-path import resolution | Unit 3 |
| R3.d — Mixed-language fixture repo indexes cleanly | Unit 4 |
| R3.e — `get_file_structure` returns uniform results across languages | Unit 4 |

## Scope Boundaries

- **In scope:** three extractor implementations, grammar registration, tree-sitter queries,
  cross-file symbol resolution per language, test fixtures, uniform integration tests.
- **Out of scope:** language-specific *semantic* analysis (delegate to LSP/R2); scripting languages
  (Ruby, PHP, Kotlin) — defer to a later plan; language-specific linters (ruff/eslint/gofmt).

## Memory Context

No relevant memory entries found.

## Context & Research

### Extension Points

- `src/cartograph/parsing/registry.py::_get_language` — dispatch table; add Go/Rust/Java.
- `src/cartograph/parsing/registry.py::ParserRegistry::language_for_file` — extension map; add
  `.go`, `.rs`, `.java`.
- `src/cartograph/parsing/queries.py` — per-language node-type sets (used by `_walk_tree`); add
  per-language entries.
- `src/cartograph/parsing/extractors.py` — triplet of `_extract_<lang>_definitions`,
  `_extract_<lang>_imports`, `_extract_<lang>_calls` plus dispatch in the public API functions.
- `src/cartograph/indexing/indexer.py::_resolve_python_import_to_file` and
  `::_resolve_ts_import_to_file` — prior art for cross-file resolution. Add
  `_resolve_go_import_to_file`, `_resolve_rust_import_to_file`, `_resolve_java_import_to_file`.

### Node-Kind Mapping (schema unchanged)

| Construct | Go | Rust | Java | Maps to |
|---|---|---|---|---|
| Function | `func` | `fn` | (static method) | `function` |
| Struct | `type X struct` | `struct X` | `class` | `class` |
| Interface | `type X interface` | `trait X` | `interface` | `interface` |
| Enum | (n/a — iota const blocks) | `enum X` | `enum` | `enum` |
| Type alias | `type X = Y` | `type X = Y` | (n/a) | `type_alias` |
| Method | `func (r X) Foo()` | `impl X { fn foo }` | `X.foo()` | `method` |
| Module / file | package | mod | package | `module` / `file` |

Rust `impl` blocks map to `contains` edges linking the impl methods to their target struct.
Java inner classes use `contains` edges to their enclosing class.

### Target Extensions

- Go: `.go` (skip `_test.go` routing is a R5 concern; still parse them).
- Rust: `.rs`.
- Java: `.java`.

## Key Technical Decisions

### Language ordering: Go → Java → Rust

Per brainstorm recommendation. Go has the smallest extractor surface (no traits, simple method
syntax, explicit `package` imports). Java is medium (classes + interfaces + package-path imports).
Rust is highest complexity (traits, `impl` blocks, `use` path resolution). Each ships behind its
own PR.

### Tree-sitter grammar versions

Pin in `pyproject.toml`:
- `tree-sitter-go>=0.25.0`
- `tree-sitter-rust>=0.25.0`
- `tree-sitter-java>=0.25.0`

All three are stable and maintained by the core tree-sitter org.

### Cross-file import resolution

Each language uses a different path convention:

- **Go:** `import "github.com/x/y"` → map via `go.mod` to module path, then to file path. For
  *relative* / same-module imports, walk up from the current file to the `go.mod` root, resolve
  the relative path. No external resolution for third-party (they're nodes without files).
- **Rust:** `use crate::foo::bar` → walk `src/` for `foo/mod.rs` or `foo.rs`, then `bar`. `use
  self::` and `use super::` are file-local. External crates are nodes without files.
- **Java:** `import com.example.Foo` → walk project `src/main/java/` (and `src/test/java/`) for
  the package path. Wildcards (`import com.example.*`) resolve to all files in that directory.

All three follow the prior-art pattern: return `None` if unresolvable, let the graph store the
`Import` as a leaf node without a file link.

### Qualified-name convention

Follow the `::` separator convention already in use:
- Go: `pkg.path::StructName::MethodName` (package + type + method). Top-level funcs:
  `pkg.path::FuncName`.
- Rust: `crate::mod::path::StructName::method` for `impl` methods; free functions:
  `crate::mod::path::func_name`.
- Java: `com.example.pkg::ClassName::methodName`. Inner classes: `com.example.pkg::Outer::Inner::method`.

The separator stays `::` for cross-language consistency (even though Rust uses `::` natively and
Java/Go use `.`). This is a Cartograph internal convention, not a language-native one.

## Open Questions

### Resolve Before Implementing

- **Go `iota` const blocks as enums?** Recommend: skip in v1 — they're not first-class `enum`
  types in Go's semantics. A `const` block becomes a group of `variable` nodes. Reconsider if a
  user asks.
- **Rust macro expansions?** Out of scope. Macros are parsed as plain function-call syntax by
  tree-sitter; `derive` macros produce no extractable methods from the AST alone. Accept the
  limitation.

### Defer

- Kotlin, Scala, C#, Ruby, PHP, Swift, C/C++ — separate future plan.

## Implementation Units

### Unit 1 — Go extractor

**State:** pending

- [ ] Add `tree-sitter-go>=0.25.0` to `pyproject.toml`.
- [ ] Register in `registry.py::_get_language("go")` and extension mapping for `.go`.
- [ ] Add Go entries to `parsing/queries.py`: node types for `function_declaration`,
      `method_declaration`, `type_declaration`, `struct_type`, `interface_type`,
      `import_declaration`, `call_expression`.
- [ ] `_extract_go_definitions`, `_extract_go_imports`, `_extract_go_calls` in
      `parsing/extractors.py`. Wire up in `extract_definitions`/`extract_imports`/`extract_calls`
      dispatchers.
- [ ] `_resolve_go_import_to_file` in `indexing/indexer.py`, keyed on `go.mod` root.
- [ ] Fixture: `tests/fixtures/go_sample/` — 3 files, one package, a struct with a method, one
      interface, one import between them.
- [ ] Tests: `tests/test_parsing_go.py` covering each extractor; `tests/test_indexing_go.py`
      covering full-repo index + `get_file_structure`.

**Verification:**
- `uv run pytest tests/test_parsing_go.py tests/test_indexing_go.py` green.
- `query_node("go_sample.main::Server::Handle")` returns the method with `contains`-edge back
  to the struct.

**Test scenarios:**
- Happy: struct with pointer-receiver method, extracted correctly.
- Edge: `interface` with embedded interface — `inherits` edge.
- Edge: blank import `_ "package"` — import recorded, no bind.
- Edge: dot import `. "package"` — import recorded.

### Unit 2 — Java extractor

**State:** pending

- [ ] Add `tree-sitter-java>=0.25.0`.
- [ ] Register in `registry.py`; extension `.java`.
- [ ] Queries: `class_declaration`, `interface_declaration`, `enum_declaration`,
      `method_declaration`, `constructor_declaration`, `import_declaration`,
      `method_invocation`, `object_creation_expression`.
- [ ] `_extract_java_definitions` (handles `class` / `interface` / `enum` / inner classes),
      `_extract_java_imports`, `_extract_java_calls`.
- [ ] `_resolve_java_import_to_file` scans `src/main/java/` and `src/test/java/`.
- [ ] Fixture: `tests/fixtures/java_sample/` — 2 packages, interface + class + inheritance +
      cross-package import.
- [ ] Tests: `tests/test_parsing_java.py`, `tests/test_indexing_java.py`.

**Test scenarios:**
- Happy: interface + impl class — `inherits` edge recorded (Java `implements`).
- Happy: `extends` → `inherits` edge.
- Edge: wildcard import `com.example.*` — resolves to all files in that directory (pessimistic:
  record edges to each file-level module).
- Edge: inner class — `contains` edge from outer to inner.
- Edge: anonymous class — represented as a `class` node with synthesized name
  `Outer::Anon_N`.

### Unit 3 — Rust extractor

**State:** pending

- [ ] Add `tree-sitter-rust>=0.25.0`.
- [ ] Register in `registry.py`; extension `.rs`.
- [ ] Queries: `function_item`, `struct_item`, `enum_item`, `trait_item`, `impl_item`,
      `type_item`, `use_declaration`, `call_expression`, `macro_invocation` (for recording
      macro calls as plain `calls` edges).
- [ ] `_extract_rust_definitions` — handles `struct` → `class`, `trait` → `interface`, `impl X
      for Y` → method nodes with `inherits` edge from X to Y,  `enum` → `enum`, `fn` → `function`
      or `method` based on parent `impl`.
- [ ] `_extract_rust_imports` — resolves `use` paths via `Cargo.toml`-rooted walk.
- [ ] `_extract_rust_calls`.
- [ ] `_resolve_rust_import_to_file` — walks `src/` for `mod.rs` / `<name>.rs` alternatives.
- [ ] Fixture: `tests/fixtures/rust_sample/` — lib crate, trait + struct + impl, one `use`
      crossing modules.
- [ ] Tests: `tests/test_parsing_rust.py`, `tests/test_indexing_rust.py`.

**Test scenarios:**
- Happy: `trait Foo { fn bar(); }` + `impl Foo for MyStruct` — `inherits` edge from MyStruct to
  Foo; `contains` edges for impl methods.
- Edge: generic function `fn foo<T>()` — parameter `T` not treated as a definition.
- Edge: macro `println!()` invocation recorded as a `calls` edge to a synthesized
  `std::macros::println` node.
- Edge: workspace-member crates — out of scope; single-crate fixture only for v1.

### Unit 4 — Mixed-language integration

**State:** pending

- [ ] Fixture: `tests/fixtures/polyglot/` — one tiny Python + Go + Rust + Java mini-monorepo.
- [ ] Test: `tests/test_polyglot_indexing.py` — runs `Indexer.index_all()` over the fixture,
      asserts all languages appear with expected node counts and that `get_file_structure` returns
      uniform results (same keys, same shape) across languages.
- [ ] Smoke assertion: `rank_by_in_degree` returns nodes across ≥3 languages (proving the graph
      is truly polyglot, not siloed).

**Test scenarios:**
- Happy: polyglot index runs without errors; `annotation_status()` shows all nodes pending.
- Edge: a file with a non-registered extension (e.g., `.c`) is silently skipped with a debug log.

### Unit 5 — Documentation

**State:** pending

- [ ] Update `README.md` supported-languages list.
- [ ] Update `CLAUDE.md` conventions section — add Go/Java/Rust qualified-name examples.
- [ ] Update `plugins/kitty/skills/kitty/SKILL.md` language-coverage note.

**Files:** `README.md`, `CLAUDE.md`, `plugins/kitty/skills/kitty/SKILL.md` (modify).

## System-Wide Impact

- **Extractor surface** grows from 2 (python, typescript-family) to 5 languages.
- **Dependencies:** +3 tree-sitter grammars. Each grammar is ~1–5 MB wheel.
- **Indexing time:** proportional to code size in new languages; parser cache in `registry.py`
  amortizes over files.
- **Schema:** unchanged. All new constructs fit existing kinds.
- **Agents:** no prompt changes strictly required — agents that already work for Python/TS work
  for Go/Rust/Java. Skill tool-reference docs should mention expanded coverage.

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| Rust grammar has breaking API change between minor versions | Pin version; CI smoke-tests grammar initialization |
| Cross-file resolution misses ~20% of imports due to build-system edge cases | Accept — record unresolved imports as leaf nodes; this matches Python behavior for third-party imports |
| Java inner-class naming collides with outer class of same name in sibling file | Use fully-qualified package-based names; unit-test this |
| Go generics (type parameters) confuse the extractor | Test fixture includes generics; skip type-param definitions (they're not top-level symbols) |

**Dependencies on other plans:** none. R2 (LSP) benefits from R3 languages but is not required.
R5 (test coverage) depends on R3 to discover Go/Java/Rust test functions.

## Sources & References

- Origin: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R3)
- Predecessor plan: `docs/plans/2026-04-23-004-feat-language-expansion-plan.md` (refreshed by this plan)
- tree-sitter-go: https://github.com/tree-sitter/tree-sitter-go
- tree-sitter-rust: https://github.com/tree-sitter/tree-sitter-rust
- tree-sitter-java: https://github.com/tree-sitter/tree-sitter-java

## Handoff

Ready for `kitty:work`. Entry point: Unit 1 (Go). Units 1, 2, 3 independent; any order. Unit 4
is the integration gate and must run after all three merge.
