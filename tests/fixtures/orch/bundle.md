# Context Bundle — fixture (orchestration-script tests)

This is a tiny fixture Context Bundle used by the behavioral runner in
`tests/test_orchestration_scripts.py` and by the orchestrator's live smoke test
of `review.orch.js`. It follows `references/bundle-format.md` (sections in order)
but is deliberately minimal. Every node and path below references a REAL symbol so
the live smoke test reads genuine source rather than a dangling reference.

## Target nodes

- `cartograph.parsing.registry::ParserRegistry::parse_file` — method — role: parser —
  tags: [tree-sitter, parse] — `src/cartograph/parsing/registry.py:78-83`
- `cartograph.parsing.extractors::extract_definitions` — function — role: extraction —
  tags: [ast, definitions] — `src/cartograph/parsing/extractors.py:1465-1480`
- `cartograph.indexing.discovery::discover_files` — function — role: discovery —
  tags: [walk, glob] — `src/cartograph/indexing/discovery.py:93-134`

## File structures

### `src/cartograph/parsing/registry.py`
- `ParserRegistry` (class) — tree-sitter parser registry keyed by language.
  - `get_parser` (method) — resolves the `(Parser, Language)` pair for a file.
  - `parse_file` (method) — reads a file's bytes and returns the parsed `Tree`.

### `src/cartograph/parsing/extractors.py`
- `extract_definitions` (function) — walks a parsed `Tree` and returns the
  `Definition` records for the file's language.

### `src/cartograph/indexing/discovery.py`
- `discover_files` (function) — yields source paths under the project root,
  honoring `EXCLUDED_DIRS` and `.gitignore` patterns.

## Memory lessons (litter/treat)

### Litter lessons to avoid
- `[anti-pattern]` Do not re-parse unchanged files; indexing is incremental.
  Context: `src/cartograph/indexing/`

### Treat lessons to follow
- `[convention]` Qualified names use the `::` separator.
  Context: `cartograph.parsing.extractors::extract_definitions`

### Memory gaps
- No relevant entries found for "concurrency".
