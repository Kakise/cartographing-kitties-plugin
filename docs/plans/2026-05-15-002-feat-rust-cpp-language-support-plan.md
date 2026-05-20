---
title: Rust & C++ Language Support
type: feat
status: in_progress
date: 2026-05-15
origin: docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md
requirement: R3
units:
  - id: 1
    title: Rust extractor
    state: complete
  - id: 2
    title: C++ extractor
    state: complete
  - id: 3
    title: Mixed-language integration
    state: complete
  - id: 4
    title: Documentation & validator updates
    state: pending
---

# Rust & C++ Language Support — Implementation Plan

## Overview

Add tree-sitter-driven extraction for Rust and C++ so the framework covers two of the most-requested
systems languages. Each language gets a self-contained extractor module that maps onto the existing
`Definition` / `Import` / `CallSite` dataclasses and the existing node/edge kinds — no schema
changes. Ships per-language (Rust first, C++ second). Each unit can merge independently.

This plan narrows and supersedes the Rust slice of
`docs/plans/2026-05-04-005-feat-language-expansion-plan.md` (Unit 3 of that plan). Go and Java
remain in the older plan; this one focuses on the Rust + C++ pair the user requested.

## Problem Frame

`src/cartograph/parsing/registry.py::EXTENSION_MAP` and `_get_language` hard-code five extensions
across four grammars (Python, TS, TSX, JS). `src/cartograph/parsing/extractors.py::extract_*`
dispatchers fall through to `[]` for any other language. `src/cartograph/indexing/discovery.py::DEFAULT_EXTENSIONS`
also gates discovery to those five suffixes — so Rust and C++ files are not even *enumerated*
today. Tree-sitter grammars for both languages are stable and have first-party Python wheels.

## Requirements Trace

| Requirement | Implementation Unit |
|---|---|
| R3 — Rust parser, extractors, module-path import resolution | Unit 1 |
| R3 — C++ parser, extractors, header-include resolution | Unit 2 |
| R3 — Mixed-language fixture indexes cleanly; uniform `get_file_structure` results | Unit 3 |
| R3 — Documentation updated; validator knows the new languages | Unit 4 |

## Scope Boundaries

- **In scope:** Rust + C++ extractor implementations, grammar registration, discovery extension
  list, per-language tree-walk node-type sets, cross-file import/include resolution, test
  fixtures, uniform integration tests, README/CLAUDE.md/SKILL.md doc updates.
- **Out of scope:** plain C (separate grammar, separate plan); semantic analysis (LSP — R2);
  preprocessor evaluation (`#define` / `#ifdef` expansion); Cargo workspace member crates;
  CMake/Meson build-system reasoning; macro expansion in Rust (`derive` and procedural macros
  do not produce extractable methods from the AST alone); template specialization tracking.

## Memory Context

- Treat lessons to follow:
  - [validated-pattern] Skills `allowed-tools` validation is enforced by
    `scripts/validate_skills.py::KNOWN_TOOLS`. No new MCP tool is introduced here, so KNOWN_TOOLS
    is not affected. — Surfaced while landing harness-followup work.
  - [convention] Per-unit `**State:**` lines in `docs/plans/*.md` must be standalone paragraphs
    using the taxonomy `pending | in_progress | complete | skipped`. — Applied in this plan's
    frontmatter and unit headers.
- Litter lessons to avoid:
  - No directly relevant negative entries found for extractor authoring or language registration.
- Memory gaps:
  - No prior memory about tree-sitter-rust or tree-sitter-cpp grammar quirks — record any
    surprises (e.g., grammar API changes between minor versions) as treats when they surface.

## Context & Research

### Annotation Status

The current graph is fully annotated and stable (per the brainstorm: 946 annotated nodes, 0 pending,
0 stale at brainstorm time). No annotation reseeding is required to plan this work.

### Extension Points (verified by reading current source)

- `src/cartograph/parsing/registry.py::EXTENSION_MAP` (lines 13–19) — extension dispatch table;
  add `.rs`, `.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.h` (see "C++ header
  extension caveat" below).
- `src/cartograph/parsing/registry.py::_get_language` (lines 22–33) — language-name → `Language`
  dispatch; add `rust` and `cpp` branches importing `tree_sitter_rust` / `tree_sitter_cpp`.
- `src/cartograph/parsing/queries.py` — add Rust and C++ entries to `QUERIES` for documentation,
  and add the corresponding `RUST_*_TYPES` / `CPP_*_TYPES` sets for the tree-walker.
- `src/cartograph/parsing/extractors.py` — add `_extract_rust_definitions/_imports/_calls` and
  `_extract_cpp_definitions/_imports/_calls`; wire the dispatchers in `extract_definitions` /
  `extract_imports` / `extract_calls` (currently fall-through `else: return []` at lines ~580–648).
- `src/cartograph/indexing/discovery.py::DEFAULT_EXTENSIONS` (line 15) — discovery gates files by
  suffix; if extensions are not added here, the indexer never even sees Rust/C++ files. **Critical.**
- `src/cartograph/indexing/indexer.py::_resolve_python_import_to_file` (lines 85–130) and
  `::_resolve_ts_import_to_file` (lines 133–162) — prior art. Add `_resolve_rust_use_to_file` and
  `_resolve_cpp_include_to_file`. Hook into the resolution loop at line ~388–390 in
  `_index_files` where the language switch lives.
- `src/cartograph/indexing/indexer.py::_module_path_for_file` (lines 40–64) — converts a relative
  path to a dotted module path used for cross-file resolution; extend the language switch (or
  leave the existing dotted-path output untouched and key Rust/C++ resolution off the relative
  path directly — see Key Technical Decisions).

### Node-Kind Mapping (schema unchanged)

| Construct | Rust | C++ | Maps to |
|---|---|---|---|
| Function (free) | `fn foo()` | free function | `function` |
| Class-like aggregate | `struct X` | `class X` / `struct X` | `class` |
| Interface-like | `trait X` | abstract class / pure-virtual | `interface` (Rust) / `class` (C++) |
| Enum | `enum X` | `enum`, `enum class` | `enum` |
| Type alias | `type X = Y` | `using X = Y`, `typedef Y X` | `type_alias` |
| Method | `impl X { fn foo() }` | `X::foo()` (inline or out-of-line) | `method` |
| Module / file | `mod`, file | namespace, file | `module` / `file` |

Rust `impl X for Y` blocks produce a `inherits` edge from `Y` (the implementing type) to `X` (the
trait), plus `contains` edges from `Y` to the impl-block methods. C++ class inheritance
(`class D : public B`) produces an `inherits` edge from `D` to `B` per base class. C++ namespaces
become `module` nodes whose qualified name is the namespace path.

### Target Extensions

- **Rust:** `.rs` (single suffix; trivial).
- **C++:**
  - Source: `.cpp`, `.cc`, `.cxx`, `.c++`.
  - Headers: `.hpp`, `.hh`, `.hxx`, `.h++`, `.h`.
  - **C++ header extension caveat:** `.h` is also used by pure C and by some mixed-language
    projects. v1 maps `.h` to the C++ grammar pragmatically — tree-sitter-cpp accepts C-style code
    as a syntactic subset, so plain-C `.h` files will still parse without errors (they just won't
    surface C++-specific constructs that aren't present). Record this in the README "Supported
    Languages" table and in the C++ extractor's module docstring. Reconsider when a C grammar is
    added in a future plan.

### Key Symbol Details (call sites needing changes)

- `extractors.py::extract_definitions` (~line 575): currently
  `if language == "python": ... elif language in ("typescript", "tsx", "javascript"): ... else: return []`.
  Add `elif language == "rust": return _extract_rust_definitions(root, fp)` and
  `elif language == "cpp": return _extract_cpp_definitions(root, fp)`. Repeat for `extract_imports`
  and `extract_calls`.
- `indexer.py::_index_files` (~line 386): `if language == "python": ... elif language in (...): ...`
  branch governs which resolver is called. Add Rust and C++ branches.

### Importance Ranking

The three highest-centrality nodes that this work changes:
1. `cartograph.parsing.extractors::extract_definitions` (and siblings) — public API, called by the
   indexer for every file.
2. `cartograph.parsing.registry::ParserRegistry::get_parser` — single dispatch point for every
   parse call.
3. `cartograph.indexing.discovery::discover_files` — gates which files even reach parsing.

All three are touched by adding any language. The Rust+C++ pair is contained: it does not change
storage, MCP server, annotation, or memory subsystems.

### Cross-File Resolution Strategy

**Rust:**
- `use crate::foo::bar;` → walk `src/`-rooted module hierarchy: look for `foo/mod.rs` or `foo.rs`,
  then inside that file resolve `bar`. For v1, resolve to the *file* (`foo/mod.rs` or `foo.rs`) and
  let definition-name resolution downstream link the import to the named item.
- `use self::x;` and `use super::x;` are scoped relative to the current file's `mod` parent.
  Treat `self::` as same-file, `super::` as one directory up.
- `use std::...` and `use external_crate::...` are leaves with no file resolution. Record the
  import as a leaf node (matches Python's behavior for third-party imports).
- Cargo workspace member crates are **out of scope** for v1. Single-crate fixture only.

**C++:**
- `#include "foo.h"` → resolve relative to the source file's directory. If not found, fall back
  to walking from `include/`-style sibling directories (one upward hop). Record as leaf if
  unresolved.
- `#include <foo>` → system or third-party. Always a leaf; never resolve to repo files.
- Out-of-line method definitions (`void Foo::bar() { ... }` in `foo.cpp`) need to be linked back
  to class `Foo`. v1 strategy: extract the method with qualified name `Foo::bar`, then in the
  cross-file resolution phase, match against any existing class node whose qualified name ends
  with `::Foo` or equals `Foo`. If a match is found, emit a `contains` edge. If not, the method
  becomes a standalone function-like node (acceptable degraded behavior — better than crashing).
- Anonymous namespaces (`namespace { ... }` inside a `.cpp`) — treat as file-local; do not create
  a namespace node, but children still get parented to the file.

### Qualified-Name Conventions

Per the existing repo convention, qualified names use `::` as the separator (already documented in
`CLAUDE.md`):

- **Rust:** `crate::mod::path::StructName::method_name` for impl methods; `crate::mod::path::func`
  for free functions; `crate::mod::path::TraitName` for traits. The leading `crate::` is dropped
  in v1 — we key off the file's module path so qualified names start at the top-level module
  (matches existing Python/TS practice of stripping `src/`).
- **C++:** `ns::sub_ns::ClassName::method` for methods (in-class or out-of-line);
  `ns::sub_ns::FreeFunction` for namespace-scoped free functions; `ClassName` (no namespace prefix)
  for global-namespace classes. Anonymous namespaces yield names like
  `(anon@<file_path>)::ClassName` only when the parent scope is needed for disambiguation.

The `::` separator is already C++ and Rust's native delimiter — convenient.

### Transitive Dependencies (what the target area depends on)

- `tree-sitter` (already pinned `>=0.25.0`).
- New: `tree-sitter-rust` and `tree-sitter-cpp` Python wheels.

### Transitive Dependents (what depends on the target area)

- Every MCP tool that returns node data (`query_node`, `get_file_structure`, `search`, …) — they
  receive *more* nodes once the new languages index, but no structural changes required.
- `kitty:work` / `kitty:review` / `kitty:plan` skill flows — operate over the polyglot graph
  without prompt changes.

### Blast Radius (depth 3)

- **Depth 1 (direct touch):** `parsing/registry.py`, `parsing/extractors.py`, `parsing/queries.py`,
  `indexing/discovery.py`, `indexing/indexer.py`, `pyproject.toml`.
- **Depth 2 (consumer surface):** `server/tools/*` (read-only consumers of the public extract_*
  and ParserRegistry surfaces), `annotation/*` (consumes nodes after they exist).
- **Depth 3 (visible to skills/agents):** every skill that calls MCP tools sees expanded coverage;
  no prompt or contract change required.

## Key Technical Decisions

### Language ordering: Rust → C++

Rust first because the extractor surface is smaller and prior research already exists in
`docs/plans/2026-05-04-005-feat-language-expansion-plan.md` (Unit 3). C++ second because the
header/source split, out-of-line method definitions, and preprocessor surface are materially
harder. Each unit ships behind its own PR.

### Tree-sitter grammar versions

Pin in `pyproject.toml`:
- `tree-sitter-rust>=0.25.0`
- `tree-sitter-cpp>=0.25.0`

Both are first-party tree-sitter org grammars with stable Python wheels and PyPI distributions
matching the tree-sitter 0.25 series we already depend on. CI smoke-tests grammar initialization
(`Language(tree_sitter_rust.language())`) on each runtime in the matrix (Python 3.13, 3.14).

### Discovery extension list — single source of truth

Currently `EXTENSION_MAP` in `registry.py` and `DEFAULT_EXTENSIONS` in `discovery.py` are
maintained independently. Both must be updated. v1 keeps them duplicated (consistent with the
existing pattern); a future refactor could derive `DEFAULT_EXTENSIONS` from `EXTENSION_MAP.keys()`,
but doing that here is out of scope.

### C++ out-of-line methods: name-based resolution in cross-file phase

Out-of-line method definitions are the highest-impact C++ design call. The decision: extract
methods with their fully-qualified name (`Foo::bar`) as a `method`-kind node, then during the
cross-file resolution phase already present in `_index_files` (where Python and TS imports are
resolved), do a name-match against existing class nodes. If a class with qualified name `Foo` (or
ending in `::Foo`) exists, emit a `contains` edge from the class to the method. If not (because
the class lives in a header that hasn't been parsed yet, or the user only indexed implementation
files), record the method as standalone. This is a known imperfection; document it.

### Rust impl-block method handling

`impl X { fn foo() }` produces a `method` node with qualified name `X::foo` and a `contains` edge
from the struct/enum X to the method. `impl Trait for X { fn foo() }` produces both: a `contains`
edge from X to the method **and** an `inherits` edge from X to the trait. Tree-sitter-rust exposes
the `impl_item` node with a `trait:` field that we use to detect the trait-impl form.

### Skip macro and template instantiation tracking

Rust `macro_invocation` and C++ template-parameter / template-instantiation nodes are visited by
the tree walker only enough to emit `calls` edges for macro invocations (`println!()` → call to
a synthesized `println` node). Template type parameters (`<T>`) and Rust generic parameters do
not produce definition nodes. This matches the brainstorm scope and avoids exploding the graph.

## Open Questions

### Resolve Before Implementing

- **Rust macros (`macro_rules!`, `proc_macro`):** Out of scope. Record macro *invocations* as
  plain `calls` edges; do not extract the macro definition itself. Reconsider if users ask.
- **C++ `#define` and conditional compilation:** Out of scope. tree-sitter-cpp parses the
  directives without expanding them; macro-defined symbols therefore won't appear as nodes.
  Accept the limitation; document it in README.
- **`.h` ambiguity (C vs C++):** Map `.h` to C++ in v1. tree-sitter-cpp accepts the C subset
  syntactically, so plain-C headers parse without errors and contribute file nodes plus any
  function/struct declarations they expose. Document this. Add a C grammar in a future plan.

### Defer

- **Pure C, C#, Kotlin, Scala, Swift, Ruby, PHP** — future per-language plans.
- **Cargo workspace member crates, CMake/Meson build graphs** — separate "build-system integration"
  plan; this plan stops at single-crate Rust and source-tree C++.
- **Bridging Rust→C++ FFI calls (`extern "C"`)** — separate cross-language interop plan.

### Pipeline-mode implicit choices (auditable)

If this plan is consumed by `kitty:lfg` rather than interactively, the implementer should pick:
- `.h` → C++ grammar (Recommended).
- `tree-sitter-cpp` version `>=0.25.0` (matches existing pin policy).
- Single-crate Rust scope (no workspaces) for v1.

## Implementation Units

### Unit 1 — Rust extractor

**State:** complete

- [ ] Add `tree-sitter-rust>=0.25.0` to `pyproject.toml`; run `uv lock` to refresh `uv.lock`.
- [ ] Register `rust` in `src/cartograph/parsing/registry.py::_get_language`; add `.rs` to
      `EXTENSION_MAP`.
- [ ] Add `.rs` to `DEFAULT_EXTENSIONS` in `src/cartograph/indexing/discovery.py`.
- [ ] Add `QUERIES["rust"]` documentation block in `src/cartograph/parsing/queries.py` and the
      `RUST_DEF_TYPES`, `RUST_IMPORT_TYPES`, `RUST_CALL_TYPES` sets (using the tree-sitter-rust
      node names: `function_item`, `struct_item`, `enum_item`, `trait_item`, `impl_item`,
      `type_item`, `use_declaration`, `call_expression`, `macro_invocation`).
- [ ] Implement `_extract_rust_definitions`, `_extract_rust_imports`, `_extract_rust_calls` in
      `src/cartograph/parsing/extractors.py`. Wire the three public dispatchers (lines ~575–648).
- [ ] Implement `_resolve_rust_use_to_file` in `src/cartograph/indexing/indexer.py`, walking
      `src/` for `<segment>/mod.rs` or `<segment>.rs`. Hook into the resolution loop in
      `_index_files` around line 386.
- [ ] Fixture: `tests/fixtures/rust_sample/Cargo.toml` (minimal) + `tests/fixtures/rust_sample/src/`
      with `main.rs`, `lib.rs`, `geometry/mod.rs`, `geometry/circle.rs` — covers struct, trait,
      `impl Trait for Type`, `use crate::geometry::Circle`, free function, method, enum.
- [ ] Tests: `tests/test_parsing_rust.py` (per-extractor unit tests against the fixture) and
      `tests/test_indexing_rust.py` (end-to-end `Indexer.index_all()` + `get_file_structure`
      smoke check).

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/cartograph/parsing/registry.py`,
  `src/cartograph/parsing/queries.py`, `src/cartograph/parsing/extractors.py`,
  `src/cartograph/indexing/discovery.py`, `src/cartograph/indexing/indexer.py`.
- Create: `tests/fixtures/rust_sample/**`, `tests/test_parsing_rust.py`,
  `tests/test_indexing_rust.py`.

**Approach:**
Mirror the Python and TypeScript extractor structure. Treat `impl X` and `impl Trait for X` as
the two forms of the `impl_item` node; differentiate by checking for the presence of the `trait:`
field. Method qualified names take the form `X::method` (consistent with native Rust path syntax
and the repo's `::` convention).

**Patterns to follow:**
- Public extractor dispatch already in `extractors.py::extract_definitions` (and siblings).
- `_walk_tree` helper from `extractors.py` for collecting target nodes.
- `_find_enclosing_class` / `_find_enclosing_scope` for parenting decisions — extend (or mirror)
  for Rust's `impl_item` scoping.
- File-node + `contains`-edge layout from `_index_files` Phase 2.

**Test scenarios:**
- Happy: `struct Circle { radius: f64 }` + `impl Circle { fn area(&self) -> f64 { ... } }` →
  class node `Circle`, method node `Circle::area`, `contains` edge between them.
- Happy: `trait Shape { fn area(&self) -> f64; }` + `impl Shape for Circle { ... }` →
  trait node `Shape` (kind `interface`), `inherits` edge from `Circle` to `Shape`, `contains`
  edges to the impl methods.
- Edge: `use crate::geometry::Circle` → import resolved to `tests/fixtures/rust_sample/src/geometry.rs`
  (or `geometry/mod.rs`).
- Edge: `use std::collections::HashMap` → import recorded as leaf, no file link.
- Edge: `use self::sibling::Foo` and `use super::parent::Bar` → resolved relative to current
  file's directory.
- Edge: generic function `fn foo<T>(...)` → `T` is not a definition.
- Edge: `println!("hi")` macro → call edge to a synthesized `println` callee.

**Verification:**
- `uv run pytest tests/test_parsing_rust.py tests/test_indexing_rust.py` green on Python 3.13 and 3.14.
- `query_node("rust_sample.geometry.circle::Circle::area")` returns the method with a `contains`
  edge from `rust_sample.geometry.circle::Circle`.
- `find_dependents("rust_sample.geometry.circle::Circle")` returns the importing file.

### Unit 2 — C++ extractor

**State:** complete

- [ ] Add `tree-sitter-cpp>=0.25.0` to `pyproject.toml`; refresh `uv.lock`.
- [ ] Register `cpp` in `registry.py::_get_language` (binding `tree_sitter_cpp.language()`);
      extend `EXTENSION_MAP` with `.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx`, `.h++`,
      `.h`.
- [ ] Extend `DEFAULT_EXTENSIONS` in `discovery.py` with the same suffix set.
- [ ] Add `QUERIES["cpp"]` documentation block plus `CPP_DEF_TYPES`, `CPP_IMPORT_TYPES`,
      `CPP_CALL_TYPES` sets in `queries.py`. Target node types: `class_specifier`,
      `struct_specifier`, `function_definition`, `function_declarator`, `namespace_definition`,
      `enum_specifier`, `enum_class_specifier`, `type_definition` (typedef), `alias_declaration`
      (`using X = Y`), `preproc_include`, `call_expression`.
- [ ] Implement `_extract_cpp_definitions`, `_extract_cpp_imports`, `_extract_cpp_calls` in
      `extractors.py`. Handle namespaces by walking ancestor `namespace_definition` nodes to
      build the qualified-name prefix. Detect out-of-line method definitions by checking for
      a `qualified_identifier` in the `function_declarator` (i.e., `Foo::bar` rather than just
      `bar`).
- [ ] Implement `_resolve_cpp_include_to_file` in `indexer.py`. Quoted includes resolve relative
      to the source file's directory; angled includes never resolve to repo files. Hook into
      `_index_files` resolution loop.
- [ ] Cross-file linking for out-of-line methods: after Phase 2 nodes are created, walk the C++
      method nodes whose qualified name contains `::` and search `def_node_ids` (or a derived
      name index) for a class whose qualified name matches the prefix. If found, emit a
      `contains` edge; otherwise leave the method standalone with a `language="cpp"` tag.
- [ ] Fixture: `tests/fixtures/cpp_sample/` with `include/shape.h` (abstract base class
      `Shape` with pure-virtual `area()`), `include/circle.h` (declares `Circle : public Shape`),
      `src/circle.cpp` (defines `Circle::area()` out-of-line), `src/main.cpp` (uses both via
      `#include "circle.h"`), plus a tiny `enum class Color` and a free function in
      a namespace.
- [ ] Tests: `tests/test_parsing_cpp.py`, `tests/test_indexing_cpp.py`. Smoke-test that
      `.h` files containing C-style code parse without errors.

**Files:**
- Modify: `pyproject.toml`, `uv.lock`, `src/cartograph/parsing/registry.py`,
  `src/cartograph/parsing/queries.py`, `src/cartograph/parsing/extractors.py`,
  `src/cartograph/indexing/discovery.py`, `src/cartograph/indexing/indexer.py`.
- Create: `tests/fixtures/cpp_sample/**`, `tests/test_parsing_cpp.py`, `tests/test_indexing_cpp.py`.

**Approach:**
The tricky part is namespace-aware qualified names and out-of-line methods. For the namespace
prefix: implement `_find_cpp_namespace_path(node)` that walks ancestors and joins the names of
each `namespace_definition` it crosses. Anonymous namespaces produce an empty segment and are
skipped in the prefix (file-local scope). For out-of-line methods: parse the
`qualified_identifier` inside the `function_declarator` to produce a method-qualified name
that already includes the class scope.

**Patterns to follow:**
- Same Phase 1 / Phase 2 split used by Python and TS extractors.
- Cross-file resolution lives in `_index_files`, not the extractor — keep that boundary clean
  for C++ too (extractor produces nodes with qualified names; resolution emits edges).

**Test scenarios:**
- Happy: `class Circle : public Shape { double area() override; }` →
  `Circle` class node, `inherits` edge `Circle → Shape`. Pure-virtual base method gets an
  `interface`-flavored class node (we keep kind `class`; mark abstract via a tag in a future
  plan if requested).
- Happy: Out-of-line `double Circle::area() { ... }` in `circle.cpp` → method node `Circle::area`
  with `contains` edge from `Circle` (resolved cross-file after the header has been parsed).
- Happy: `#include "circle.h"` from `main.cpp` → resolved to
  `tests/fixtures/cpp_sample/include/circle.h` (relative to source dir + one sibling-dir hop).
- Happy: `namespace geo { class Triangle { ... }; }` → class qualified as `geo::Triangle`.
- Edge: `#include <vector>` → import recorded as leaf, no file link.
- Edge: `enum class Color { Red, Green };` → enum node `Color`.
- Edge: `using StringList = std::vector<std::string>;` → `type_alias` node `StringList`.
- Edge: anonymous namespace inside `circle.cpp` containing a free helper → helper recorded with
  file as parent, no namespace node.
- Edge: a `.h` file containing only C-style structs/functions parses without error and produces
  the expected nodes.
- Edge: template `template<typename T> class Vec { ... };` → `Vec` recorded as class; `T` is not
  a definition.

**Verification:**
- `uv run pytest tests/test_parsing_cpp.py tests/test_indexing_cpp.py` green.
- `find_dependencies("cpp_sample.src.main")` lists at least `cpp_sample.include.circle`.
- `query_node("Circle::area")` (or namespaced equivalent) returns the method with a `contains`
  edge from `Circle`.
- `find_dependents("Shape")` returns `Circle`.

### Unit 3 — Mixed-language integration

**State:** complete

- [ ] Fixture: `tests/fixtures/polyglot_rust_cpp/` — a tiny mini-repo containing the Rust sample
      and the C++ sample side-by-side, plus a stub Python file, so the integration test exercises
      three languages in one index.
- [ ] Test: `tests/test_polyglot_rust_cpp_indexing.py` — runs `Indexer.index_all()` over the
      fixture and asserts: (a) all three languages contribute nodes, (b) `get_file_structure`
      returns the same key set across languages, (c) `rank_nodes` returns nodes from at least
      two of the new languages (proving the graph is polyglot, not siloed).
- [ ] Smoke assertion: a file with an unregistered extension (e.g. `.zig`) inside the polyglot
      fixture is silently skipped without error, the rest of the index succeeds, and
      `IndexStats.errors` is empty.
- [ ] Smoke assertion: `annotation_status()` shows all nodes pending after a fresh index over
      the polyglot fixture.

**Files:**
- Create: `tests/fixtures/polyglot_rust_cpp/**`, `tests/test_polyglot_rust_cpp_indexing.py`.

**Approach:**
Reuse the per-language fixtures by symlinking or copying — but to keep test hermeticity, copy a
minimal trimmed-down version into the polyglot fixture rather than depending on the unit fixtures.

**Test scenarios:**
- Happy: polyglot index runs without errors; both Rust and C++ nodes appear; centrality computes.
- Edge: an unsupported-extension file (e.g. `notes.zig`) sits alongside the supported files —
  silently skipped per existing discovery semantics.
- Edge: an empty C++ header (legal — produces a tiny tree with no defs) is parsed without errors.

**Verification:**
- `uv run pytest tests/test_polyglot_rust_cpp_indexing.py` green.
- Full suite (`uv run pytest`) remains green after Units 1, 2, 3 land.

### Unit 4 — Documentation & validator updates

**State:** pending

- [ ] Update `README.md` "Supported Languages" table (line 159) to add Rust and C++ rows. Note
      the `.h` C/C++ ambiguity inline.
- [ ] Update `CLAUDE.md` conventions/MCP-surface section to add Rust and C++ qualified-name
      examples (alongside the existing Python `::` convention).
- [ ] Update `plugins/kitty/skills/kitty/SKILL.md` language-coverage note (regenerated from
      `plugins/kitty/_source/skills/kitty.yaml` via `uv run python scripts/generate_skills.py`).
- [ ] Sweep `plugins/kitty/_source/skills/*.yaml` for any other language-coverage references and
      regenerate. Then run `uv run python scripts/validate_skills.py` to confirm no drift.
- [ ] If `scripts/validate_skills.py::KNOWN_TOOLS` or any validator gates on language enums,
      extend them. (Spot-check: a grep over the validator showed no language enum at time of
      writing — but verify before merge in case the codebase shifts.)
- [ ] Mark Unit 3 of `docs/plans/2026-05-04-005-feat-language-expansion-plan.md` as
      `superseded_by: docs/plans/2026-05-15-002-feat-rust-cpp-language-support-plan.md` via
      `uv run python scripts/plan_status.py set-unit ...`. Leave Go (Unit 1) and Java (Unit 2) in
      the older plan untouched.

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `plugins/kitty/_source/skills/kitty.yaml` (and any siblings
  mentioning language coverage), `docs/plans/2026-05-04-005-feat-language-expansion-plan.md`.
- Regenerate (committed): `plugins/kitty/skills/kitty/SKILL.md` and any other skills regenerated
  by the generator.

**Verification:**
- `uv run python scripts/validate_skills.py` green.
- `uv run python scripts/generate_skills.py --check` green.
- `uv run python scripts/plan_status.py audit` green; the supersession appears in the dashboard.
- `uv run pytest tests/test_plugin_packaging.py` green (catches generator drift).

## System-Wide Impact

- **Extractor surface** grows from 2 language families (Python + TS/JS) to 4 (adds Rust + C++).
  Total registered grammars: 6 (the TS family registers 3 grammars: typescript, tsx, javascript).
- **Dependencies:** +2 tree-sitter grammars. Each grammar wheel is ~1–10 MB.
- **Indexing time:** proportional to code volume in the new languages; parser caching in
  `registry.py::ParserRegistry` amortizes initialization across files.
- **Schema:** unchanged. All Rust and C++ constructs fit existing node/edge kinds.
- **Annotation:** unaffected. New nodes start pending; annotators handle any language.
- **MCP server:** unaffected — tools are language-agnostic.
- **Agents/skills:** prompts unchanged. The kitty skills' description copy may mention expanded
  language coverage (handled in Unit 4).

## Risks & Dependencies

| Risk | Mitigation |
|---|---|
| `tree-sitter-cpp` minor version bumps occasionally rename node types | Pin `>=0.25.0`; CI smoke-tests grammar initialization and parses a sample file; on grammar upgrade, run the C++ test fixture as the canary |
| `.h` files in pure-C codebases produce confusing results when parsed as C++ | Documented limitation in README; C grammar deferred to future plan; tree-sitter-cpp parses C as a subset, so the failure mode is "fewer constructs surfaced" not "crash" |
| Rust workspace member crates not handled | Out-of-scope flag in README; fixture is single-crate; future "build-system integration" plan can extend |
| C++ out-of-line method linking misses when only the .cpp is indexed and the header lives outside the indexed tree | Method recorded as standalone — degraded but non-crashing; document in C++ extractor's module docstring |
| Macros / preprocessor / generics produce phantom or missing nodes | Documented limitation; test fixtures cover the happy path explicitly |
| Cross-file resolution name-matching may falsely link unrelated `Foo::bar` to wrong class | Match must check qualified-name *prefix* + same file's transitive include set if available; for v1, accept best-effort and add a "confidence" flag in a future plan |
| New extensions in `DEFAULT_EXTENSIONS` slow indexing on large polyglot trees | Discovery is gitignore-aware and incremental — impact is bounded; benchmark in Unit 3 if needed |
| Plan-state audit drift if `docs/plans/2026-05-04-005-feat-language-expansion-plan.md` Unit 3 isn't superseded explicitly | Unit 4 covers the supersession via `scripts/plan_status.py`; pre-commit `plan_status.py audit` will catch a missed step |

**Dependencies on other plans:** none required. R2 (LSP — `docs/plans/2026-05-04-004-feat-lsp-bridge-plan.md`)
will benefit from these languages but does not gate this work. R5 (test coverage —
`docs/plans/2026-05-04-007-feat-test-coverage-edges-plan.md`) depends on R3 to discover
Rust/C++ test functions.

## Sources & References

- Origin requirement: `docs/brainstorms/2026-04-23-001-plugin-evolution-requirements.md` (R3).
- Predecessor plan: `docs/plans/2026-05-04-005-feat-language-expansion-plan.md` (Unit 3 superseded
  by this plan).
- tree-sitter-rust: https://github.com/tree-sitter/tree-sitter-rust
- tree-sitter-cpp: https://github.com/tree-sitter/tree-sitter-cpp
- Existing extractor pattern: `src/cartograph/parsing/extractors.py` (Python: lines 131–294;
  TS/JS: ~lines 350–550).
- Existing resolution pattern: `src/cartograph/indexing/indexer.py::_resolve_python_import_to_file`
  (lines 85–130), `::_resolve_ts_import_to_file` (lines 133–162).
- Plan-state conventions: `docs/architecture/plan-state-conventions.md`.

## Handoff

Ready for `kitty:work`. Entry point: Unit 1 (Rust). Units 1 and 2 are independent and can ship in
either order or in parallel; Unit 3 is the integration gate and must follow both. Unit 4 should
land in the same merge window as Unit 3 so README and the supersession audit stay in sync with
shipping behavior.
