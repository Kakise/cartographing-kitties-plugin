from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "plugins" / "kitty").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLUGIN_ROOT = REPO_ROOT / "plugins" / "kitty"
SOURCE_PATH = PLUGIN_ROOT / "_source" / "manifests" / "plugin.yaml"
TEMPLATE_DIR = PLUGIN_ROOT / "_source" / "templates"


TARGETS = {
    "manifest.claude.json.j2": PLUGIN_ROOT / ".claude-plugin" / "plugin.json",
    "manifest.codex.json.j2": PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
    "manifest.codex.root.json.j2": REPO_ROOT / ".codex-plugin" / "plugin.json",
    "manifest.gemini.json.j2": PLUGIN_ROOT / "gemini-extension.json",
    "manifest.mcp.json.j2": PLUGIN_ROOT / ".mcp.json",
}


def _load_source() -> dict[str, Any]:
    with SOURCE_PATH.open() as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{SOURCE_PATH} must contain a mapping")
    return data


def render_outputs() -> dict[Path, str]:
    source = _load_source()
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    outputs: dict[Path, str] = {}
    for template_name, target in TARGETS.items():
        rendered = env.get_template(template_name).render(**source)
        rendered = json.dumps(json.loads(rendered), indent=2, ensure_ascii=False) + "\n"
        outputs[target] = rendered
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> int:
    drifted: list[Path] = []
    for path, expected in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drifted.append(path.relative_to(REPO_ROOT))
    if drifted:
        print("Generated plugin manifests are out of date:", file=sys.stderr)
        for path in drifted:
            print(f"  - {path}", file=sys.stderr)
        print("Run `uv run python scripts/generate_manifests.py`.", file=sys.stderr)
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
