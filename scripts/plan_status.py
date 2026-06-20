"""Thin shim — the plan-state CLI now ships in the package.

Historically this file held the argparse CLI. It moved into the distributable
package at :mod:`cartograph.planning.cli` so end users (running
``uvx cartographing-kittens``) get plan tooling. This shim keeps the repo's
``scripts/plan_status.py`` entry point and pre-commit hook working, and keeps
re-exporting the public CLI symbols (e.g. ``main``, ``_branch_match``) so
existing importers continue to resolve.

Usage:
    python scripts/plan_status.py [report|audit|set-unit|set-status] ...
"""

from __future__ import annotations

from cartograph.planning.cli import (  # noqa: F401
    PLANS_DIR,
    REPO_ROOT,
    _branch_match,
    _build_parser,
    _resolve_plan,
    build_parser,
    cmd_audit,
    cmd_report,
    cmd_set_status,
    cmd_set_unit,
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
