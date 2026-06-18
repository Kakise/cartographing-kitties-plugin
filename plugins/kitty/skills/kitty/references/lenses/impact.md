# Lens: impact

The orchestrator injects this block into a `librarian-kitten` dispatch when the
research question is about the blast radius of a proposed change — what will be
affected, which tests need updating, and what risks exist.

> You are running the **impact** lens. Read your one bundle section, then assess
> the blast radius of the change in scope using the pre-computed dependent data
> in the bundle. Do not call MCP and do not explore the codebase; everything you
> need is in the bundle.

## What to look for

The bundle's Dependents section carries transitive dependents (depth 3-4) with
depth annotations, node metadata (kind, role, tags, summary, file path), and the
edge kind connecting each dependent to the target.

- **Categorize by depth.** Depth 1 = direct dependents (most affected, highest
  risk); depth 2+ = transitive dependents (may need testing, lower risk).
- **Group by role/tag.** Reveals which domain layers are affected (e.g. "3 API
  handlers, 2 validators, 5 test files").
- **Find affected tests.** Look for `test_` prefixes or `/tests/` in file paths
  among the dependents.
- **Cross-boundary risk.** When the blast radius crosses from one role category
  to another (e.g. "data access" -> "API handler"), risk is higher.
- **Edge-kind risk profiles.**
  - `inherits` = highest risk (subclass contracts may break).
  - `imports` = medium risk (consumers need updating).
  - `calls` = lower risk (usually internal to a function).
- **Overall risk.** Low (0-2 direct dependents), Medium (3-8), High (9+).
- **Memory lessons.** Repeated litter-box failures raise risk; treat-box entries
  define the expected safe patterns.

## Coverage awareness

When annotation coverage is low, role/tag grouping is less reliable — lean on
the structural depth and edge-kind data and flag reduced confidence. When
coverage is high, trust the roles to give a domain-aware picture.

## What to report

- **Symbols analyzed** — each target symbol with its kind.
- **Direct dependents (depth 1)** — files/symbols directly using the target,
  grouped by role/tag.
- **Transitive dependents (depth 2+)** — downstream effects, grouped by role/tag.
- **Affected test files** — tests covering the target or its dependents.
- **Cross-boundary risks** — where the blast radius crosses module/layer lines.
- **Memory lessons** — prior failures to avoid and validated patterns to keep.
- **Risk assessment** — Low / Medium / High with the dependent-count rationale.

## Quality bar

- Use the pre-computed dependent data in the bundle as the primary source.
- Distinguish `calls` / `imports` / `inherits` edges — different risk profiles.
- Inheritance changes are highest risk; import changes medium; call-site lowest.
- Group dependents by role/tag for a domain-aware blast-radius picture.
- Read source lines to verify a specific coupling when the bundle is thin.

If key dependents lack the data you need or the dependent tree appears truncated
in your bundle section, return `{status: 'needs_more_context'}` naming the gap;
the orchestrator will enrich the bundle and re-dispatch you once. Otherwise
return `status: 'ok'` per `agent-output-contract.md`.
