from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "plugins" / "kitty").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLUGIN_ROOT = REPO_ROOT / "plugins" / "kitty"
TEMPLATE_DIR = PLUGIN_ROOT / "_source" / "templates"
REFERENCE_DIR = PLUGIN_ROOT / "skills" / "kitty" / "references" / "tool-reference"
FAMILY_ORDER = ["index", "query", "analysis", "annotate", "memory", "reactive"]


def _schema_type(schema: dict[str, Any]) -> str:
    if "type" in schema:
        return str(schema["type"])
    if "anyOf" in schema:
        return " | ".join(str(item.get("type", "object")) for item in schema["anyOf"])
    return "object"


def _parameter_rows(parameters: dict[str, Any]) -> list[dict[str, Any]]:
    required = set(parameters.get("required", []))
    rows: list[dict[str, Any]] = []
    for name, schema in parameters.get("properties", {}).items():
        rows.append(
            {
                "name": name,
                "required": name in required,
                "type": _schema_type(schema),
                "default": schema.get("default", None),
                "schema": json.dumps(schema, indent=2, ensure_ascii=False),
            }
        )
    return rows


def _tool_family(module_name: str) -> str:
    return module_name.rsplit(".", 1)[-1]


def _load_tools() -> dict[str, list[dict[str, Any]]]:
    from cartograph.server.main import mcp

    grouped: dict[str, list[dict[str, Any]]] = {family: [] for family in FAMILY_ORDER}
    for tool in mcp._tool_manager._tools.values():  # noqa: SLF001 - generator uses FastMCP registry.
        family = _tool_family(tool.fn.__module__)
        if family not in grouped:
            grouped[family] = []
        grouped[family].append(
            {
                "name": tool.name,
                "description": tool.description.strip(),
                "parameters": _parameter_rows(tool.parameters),
                "input_schema": json.dumps(tool.parameters, indent=2, ensure_ascii=False),
                "output_schema": json.dumps(
                    tool.fn_metadata.output_schema, indent=2, ensure_ascii=False
                ),
            }
        )
    for tools in grouped.values():
        tools.sort(key=lambda item: item["name"])
    return grouped


def render_outputs() -> dict[Path, str]:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("tool-reference.md.j2")
    outputs: dict[Path, str] = {}
    for family, tools in _load_tools().items():
        if not tools:
            continue
        outputs[REFERENCE_DIR / f"{family}.md"] = template.render(
            family=family,
            title=f"{family.title()} Tools",
            tools=tools,
        )
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    for existing in REFERENCE_DIR.glob("*.md"):
        if existing not in outputs:
            existing.unlink()
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> int:
    drifted: list[Path] = []
    for path, expected in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drifted.append(path.relative_to(REPO_ROOT))
    expected_paths = set(outputs)
    for existing in REFERENCE_DIR.glob("*.md"):
        if existing not in expected_paths:
            drifted.append(existing.relative_to(REPO_ROOT))
    if drifted:
        print("Generated tool reference files are out of date:", file=sys.stderr)
        for path in sorted(drifted):
            print(f"  - {path}", file=sys.stderr)
        print("Run `uv run python scripts/generate_tool_reference.py`.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if outputs drift")
    args = parser.parse_args(argv)

    outputs = render_outputs()
    if args.check:
        return check_outputs(outputs)
    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
