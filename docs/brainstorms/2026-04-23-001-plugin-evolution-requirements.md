# Cartographing Kittens — 2026 Evolution Themes

Brainstorm date: 2026-04-23
Triggered by: "Make the concept of this plugin even better" after surveying 2026 industry trends.

## Problem Frame

Cartographing Kittens today: tree-sitter AST → SQLite graph (5 node kinds, 5 edge kinds) → FTS5 lexical search over names and LLM-written summaries → MCP exposure (13 tools, 3 prompts) → agent swarm orchestration.

The concept landed the *structural* layer well. The 2026 code-intelligence landscape has moved on in three directions that the current design does not yet cover:

1. **Hybrid retrieval is the norm.** Lexical-only (BM25/FTS5) search now consistently trails hybrid stacks (lexical + dense + graph, fused via RRF) by 10–30% recall. Cartograph has the lexical + graph legs but no dense/semantic leg.
2. **LSP has become an agent primitive.** LSAP (Language Server Agent Protocol) and LSP wrappers reduce hallucinated APIs by ~27% and mislocalized edits by ~33%. Tree-sitter gives structure; LSP gives *semantics* (types, real references, diagnostics). Cartograph currently derives references heuristically from the AST.
3. **The graph is expected to be multi-dimensional.** State-of-the-art 2026 systems (Augment Context Engine, Cursor shared indexing, GraphCoder) fold commit history, execution/coverage data, and team conventions into the same graph agents query. Cartograph is structure-only.

On top of that, the plugin caps coverage at Python / TypeScript / JavaScript — a hard adoption ceiling in a polyglot 2026 stack.

None of this invalidates the current architecture; the graph-first principle is correct and the memory system (litter-box / treat-box) is a distinctive asset. The goal of this brainstorm is to name the handful of capability thrusts that would take the plugin from "structural index for Claude" to "dominant code-intelligence substrate for agent workflows."

## Codebase Context

Verified against the live graph (946 annotated nodes, 0 pending, 0 stale — every observation below is grounded, not speculative):

- **Parsing** — `src/cartograph/parsing/registry.py` — per-language tree-sitter parsers, cached. Four grammars registered (Python, TS, TSX, JS).
- **Indexing** — `src/cartograph/indexing/discovery.py::compute_file_hash` + gitignore-aware walk. Incremental via git-diff *or* SHA256 hash — already the right primitive for real-time mode.
- **Storage** — `cartograph.storage.graph_store::GraphStore` — single `GraphStore` class (lines 21–908) owns CRUD, FTS5 search, transitive traversal. No embedding columns, no centrality, no cross-schema versioning visible in queries.
- **Server tools** — `src/cartograph/server/tools/query.py` — 7 query tools (`query_node`, `batch_query_nodes`, `get_context_summary`, `search`, `get_file_structure`, plus internal helpers). `reactive.py` adds `graph_diff` + `validate_graph`. `annotate.py` covers the annotation lifecycle.
- **Memory** — `src/cartograph/memory/memory_store.py` — dedicated SQLite-backed persistence for litter/treat boxes, logically separate from the graph.
- **Agent layer** — `plugins/kitty/agents/` — 4 librarian + 4 expert subagents, manifested for cross-runtime (Claude Code + Codex) portability. Well-positioned to absorb new tool capabilities without disrupting the skill contracts.

The extension points are already there: adding a dense-vector column on `nodes`, a new edge kind, or a new tool module (`tools/lsp.py`, `tools/history.py`) would not require restructuring.

## Requirements

Themes are ranked by `impact_on_agent_quality × alignment_with_2026_trends / implementation_cost`. Each is stated as a testable requirement so `kitty:plan` can pick any subset and spec it concretely.

### Tier 1 — Close the 2026 parity gap

- **R1. Hybrid semantic + lexical + graph search.** `search` must fuse three channels: FTS5 (existing), dense embeddings over summaries and code, and graph-centrality boost. Fusion via Reciprocal Rank Fusion (rank-based, no manual weights). Backing store: `sqlite-vec` extension on the existing SQLite file — no new service dependency. Local embedding model (e.g., `all-MiniLM-L6-v2` or a code-tuned variant) runs at annotation time. Success: on a held-out query set, hybrid recall@10 must beat the current FTS5-only baseline by ≥15%.

- **R2. LSP bridge for semantic precision.** Introduce an optional LSP client layer (`src/cartograph/lsp/`) that wraps project-local language servers (pyright, tsserver, rust-analyzer, gopls, …). Four new MCP tools: `find_references`, `goto_definition`, `get_type`, `get_diagnostics`. Policy: tree-sitter remains the bulk-index primitive; LSP is called on-demand for precision queries and for *verifying* `calls` / `inherits` edges where the AST was ambiguous. Agents get a post-edit `get_diagnostics` feedback loop. Success: measurable drop in "phantom" call edges on a reference corpus, and agents can resolve cross-file references without grep fallbacks.

- **R3. Expanded language coverage.** At minimum: Go, Rust, Java. Each needs a parsing extractor (`src/cartograph/parsing/extractors/<lang>.py`) producing the same node/edge kinds. Tree-sitter grammars already exist. Success: a repo containing all supported languages indexes cleanly and `get_file_structure` works uniformly across them.

### Tier 2 — Multi-dimensional graph

- **R4. Commit-history dimension.** New edge kinds `authored_by`, `co_changed_with`, plus per-node fields `last_touched_at`, `change_frequency`. Populated from `git log` at index time, incremental on each run. Enables queries like *"functions that historically change together with X"* — uniquely valuable for review and refactor planning. Integrates cleanly with the existing `memory` concept (the "why" of changes can be pulled from commit messages into the treat/litter box).

- **R5. Test-coverage edges.** New edge kind `tests` linking test functions to the symbols they exercise. Derived in two passes: (a) heuristic — test function name matches target, (b) optional — parse coverage.py / nyc JSON reports to upgrade heuristics to ground truth. Enables `find_tests_for(symbol)` as a first-class query. Directly improves `expert-kitten-testing` accuracy.

- **R6. Centrality & re-ranking surface.** Expose PageRank-style centrality and in/out-degree as queryable node fields (computed lazily on index change, cached). Use it to (a) rank `search` ties, (b) prune `get_context_summary` output to the K most central nodes when a file is large. Prevents the "wall of neighbors" context blowout.

### Tier 3 — Agent-native experience

- **R7. Watch mode / live graph subscription.** File-system watcher re-indexes on save (sub-second for single-file changes). New MCP tool `subscribe_graph_changes` that streams `graph_diff` deltas so agents can react to their own edits without polling. Builds on the existing `graph_diff` tool.

- **R8. Shared / remote graph cache.** Support for publishing `.pawprints/graph.db` to a team-accessible location (S3, HTTP URL, or git-tracked compressed artifact) so teammates pull instead of re-indexing from scratch. Onboarding time drops from minutes to seconds on large monorepos, matching Cursor's shared-team-indexing UX.

- **R9. Annotation quality gates & acceleration.** Two-part:
  - Detect low-quality summaries (e.g., "Code node representing unknown in the system." currently present on 5+ annotated nodes — verified) and auto-requeue them. Heuristics: placeholder phrases, summaries shorter than N chars, summaries that don't reference the node name.
  - Tiered annotation — first pass with a fast local model (Haiku-4.5 or equivalent local 7B) for obvious cases; escalate to a larger model only for high-centrality or long/complex nodes.

### Tier 4 — Further candidates (de-prioritized, captured for later)

- **R10. Multi-repo / polyrepo graph.** Linked graphs across related services with cross-repo edges (via shared protos, OpenAPI specs, or explicit link files).
- **R11. Intent-aware prompts.** New MCP prompts: `prepare-for-refactor`, `find-dead-code`, `suggest-extract-function` — encoded workflows for common agent intents.
- **R12. Anti-pattern detector.** Tag nodes with architectural smells (god class, circular imports, feature envy) inferred from graph structure. Feeds `kitty:review`.
- **R13. Visualization export.** Mermaid / GraphViz export of dependency subgraphs — useful for generated docs and PR descriptions.
- **R14. NL→query tool.** A single MCP tool that translates natural-language structural questions into the appropriate composition of the existing tools, reducing round-trips.

## Success Criteria

- Each Tier 1 requirement has a measurable baseline and target (see individual Rs).
- The plugin retains its inline-first, Cartograph-MCP-as-primary-intelligence principle — no new capability may require running an external service by default.
- `kitty:plan` can pick any single requirement (e.g., R1 alone) and produce a coherent implementation plan without having to pull in others.

## Scope Boundaries

- **In scope:** all themes R1–R9 as separate plannable units; R10–R14 captured but not promoted.
- **Out of scope (this brainstorm):** concrete implementation plans (that's `kitty:plan`), rewrites of the SQLite substrate, rearchitecting the MCP surface, and any change that would break the Codex manifest contract.

## Key Decisions

- **Hybrid retrieval before LSP.** R1 ships value to every query; R2 is higher-effort (LSP lifecycle management, per-language server bootstrapping) and payoff is bounded to precision-sensitive tools. Sequence accordingly.
- **Stay on SQLite.** Every Tier 1/2 requirement is achievable with SQLite + `sqlite-vec` + additional tables. Introducing Qdrant/Weaviate would betray the "zero-service" property that makes the plugin pleasant to install.
- **Commit history is the unique differentiator.** Structural graphs are increasingly commoditized (GitNexus, CocoIndex, Augment). The litter-box/treat-box + commit-history combination — persistent "why" memory tied to *when* code changed — is a defensibly unique position. R4 deserves priority over R5 on that basis alone.
- **LSP wraps, does not replace.** Tree-sitter stays the indexing backbone; LSP is additive, invoked per-query, fallback-tolerant.

## Open Questions

### Resolve Before Planning

- **Embedding model choice for R1.** CPU-only local (MiniLM) keeps the zero-service promise but sacrifices code-awareness. A code-tuned model (e.g., `CodeRankEmbed`, `jina-embeddings-v2-base-code`) is stronger but larger. Decision needed before R1 is plannable.
- **LSP lifecycle ownership for R2.** Does Cartograph spawn and manage LSP processes itself, or delegate to an already-running IDE server? First is portable (CI friendly); second is lighter-weight.
- **Scope of R3 for v1.** Go + Rust + Java together, or stagger (Go first, others behind)?

### Deferred

- **Dense embeddings on code chunks vs. summaries only.** Summaries-only is cheaper and leverages the existing annotation pipeline; code chunks are richer but increase DB size materially. Empirical question — defer until R1 has a baseline.
- **Whether R7 (watch mode) should be a Cartograph concern or a harness-level hook.** Could be resolved by the Claude Code hooks system rather than baked into the MCP server.
- **Whether R8 (shared graph) should ship as an artifact format (git-tracked) or a service (pull from URL).** Depends on team-scale evidence we don't yet have.

## Research Sources (2026)

- Hybrid retrieval & RRF fusion: [GraphRAG Complete Guide 2026](https://calmops.com/ai/graphrag-complete-guide-2026/), [Hybrid Search Guide April 2026](https://blog.supermemory.ai/hybrid-search-guide/), [Dense vs Sparse Retrieval](https://dev.to/qvfagundes/dense-vs-sparse-retrieval-mastering-faiss-bm25-and-hybrid-search-4kb1)
- LSP / LSAP for agents: [LSAP on GitHub](https://github.com/lsp-client/LSAP), [LSP Integrations Transform Coding Agents](https://tech-talk.the-experts.nl/give-your-ai-coding-agent-eyes-how-lsp-integration-transform-coding-agents-4ccae8444929), [LSP vs AI-Native Architectures](https://softwareguide.medium.com/language-server-protocol-lsp-vs-ai-native-architectures-f1bd313e6a87)
- Code knowledge graphs + RAG: [Context-Augmented Code Generation with PKGs](https://arxiv.org/abs/2601.20810), [Awesome-GraphRAG](https://github.com/DEEP-PolyU/Awesome-GraphRAG), [Graph RAG Survey](https://dl.acm.org/doi/10.1145/3777378)
- Tree-sitter indexing baselines: [CocoIndex Realtime](https://github.com/cocoindex-io/realtime-codebase-indexing), [GitNexus client-side knowledge graph](https://github.com/abhigyanpatwari/GitNexus), [Opencode Codebase Index](https://github.com/Helweg/opencode-codebase-index)
- MCP & agent context practices: [Claude Code context discipline 2026](https://techtaek.com/claude-code-context-discipline-memory-mcp-subagents-2026/), [Building agents that reach production systems with MCP](https://claude.com/blog/building-agents-that-reach-production-systems-with-mcp)
