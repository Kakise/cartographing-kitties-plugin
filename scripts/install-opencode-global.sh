#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OPENCODE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
SKILLS_DIR="${OPENCODE_DIR}/skills"
COMMANDS_DIR="${OPENCODE_DIR}/commands"
AGENTS_DIR="${OPENCODE_DIR}/agents"
CONFIG_PATH="${OPENCODE_DIR}/opencode.json"

link_dir() {
  local src_dir="$1"
  local dest_dir="$2"

  mkdir -p "$dest_dir"
  for path in "$src_dir"/*; do
    local name
    name="$(basename "$path")"
    ln -sfn "$path" "$dest_dir/$name"
    printf 'Linked %s -> %s\n' "$dest_dir/$name" "$path"
  done
}

mkdir -p "$SKILLS_DIR" "$COMMANDS_DIR" "$AGENTS_DIR"

link_dir "$REPO_ROOT/.opencode/skills" "$SKILLS_DIR"
link_dir "$REPO_ROOT/.opencode/commands" "$COMMANDS_DIR"
link_dir "$REPO_ROOT/.opencode/agents" "$AGENTS_DIR"

python3 - <<'PY' "$CONFIG_PATH"
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()

if config_path.exists():
    try:
        data = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"Refusing to modify {config_path}: invalid JSON ({exc})"
        )
else:
    data = {"$schema": "https://opencode.ai/config.json"}

if not isinstance(data, dict):
    raise SystemExit(f"Refusing to modify {config_path}: root JSON value must be an object")

mcp = data.setdefault("mcp", {})
if not isinstance(mcp, dict):
    raise SystemExit(f"Refusing to modify {config_path}: 'mcp' must be an object")

mcp["kitty"] = {
    "type": "local",
    "command": ["uvx", "cartographing-kittens"],
    "enabled": True,
    "environment": {
        "KITTY_PROJECT_ROOT": ".",
    },
}

config_path.parent.mkdir(parents=True, exist_ok=True)
config_path.write_text(json.dumps(data, indent=2) + "\n")
print(f"Updated {config_path} with the kitty MCP server")
PY

printf '\nGlobal OpenCode install complete.\n'
printf 'Restart OpenCode, then use commands like /kitty-plan or /kitty-review in any repo.\n'
