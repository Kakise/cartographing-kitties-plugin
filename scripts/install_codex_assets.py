from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


def _repo_root() -> Path:
    candidates = [Path.cwd(), Path(__file__).resolve().parents[1]]
    for candidate in candidates:
        if (candidate / "plugins" / "kitty").exists() and (candidate / "pyproject.toml").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _repo_root()
PLUGIN_ROOT = REPO_ROOT / "plugins" / "kitty"
SOURCE_AGENTS = PLUGIN_ROOT / ".codex" / "agents"
SOURCE_SKILLS = PLUGIN_ROOT / "skills"
SOURCE_PROMPTS = PLUGIN_ROOT / "prompts"


@dataclass(frozen=True)
class InstallLayout:
    agents: Path
    skills: Path
    prompts: Path


def _resolve_layout(target: Path, layout: str) -> InstallLayout:
    target = target.expanduser().resolve()
    if layout == "auto":
        layout = "jetbrains" if (target / ".codex").exists() else "home"
        if target.name == ".codex":
            layout = "home"

    if layout == "home":
        return InstallLayout(
            agents=target / "agents",
            skills=target / "skills",
            prompts=target / "prompts",
        )
    if layout == "jetbrains":
        return InstallLayout(
            agents=target / ".codex" / "agents",
            skills=target / "skills",
            prompts=target / "prompts",
        )
    raise ValueError(f"unsupported layout: {layout}")


def _copy_file(source: Path, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return 1


def _copy_tree_contents(source: Path, destination: Path) -> int:
    if not source.exists():
        return 0
    copied = 0
    destination.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir()):
        if child.name in {".git", "__pycache__"}:
            continue
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(
                child,
                target,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            copied += sum(1 for path in child.rglob("*") if path.is_file())
        else:
            copied += _copy_file(child, target)
    return copied


def _delete_owned(layout: InstallLayout) -> int:
    deleted = 0
    for source in SOURCE_AGENTS.glob("*.toml"):
        target = layout.agents / source.name
        if target.exists():
            target.unlink()
            deleted += 1
    for source in SOURCE_SKILLS.glob("*/SKILL.md"):
        target = layout.skills / source.parent.name
        if target.exists():
            shutil.rmtree(target)
            deleted += 1
    for source in SOURCE_PROMPTS.glob("*.md"):
        target = layout.prompts / source.name
        if target.exists():
            target.unlink()
            deleted += 1
    return deleted


def install(target: Path, *, layout_name: str, delete_old: bool) -> dict[str, int | str]:
    layout = _resolve_layout(target, layout_name)
    deleted = _delete_owned(layout) if delete_old else 0

    agents = _copy_tree_contents(SOURCE_AGENTS, layout.agents)
    skills = _copy_tree_contents(SOURCE_SKILLS, layout.skills)
    prompts = _copy_tree_contents(SOURCE_PROMPTS, layout.prompts)

    return {
        "layout": layout_name,
        "agents_dir": str(layout.agents),
        "skills_dir": str(layout.skills),
        "prompts_dir": str(layout.prompts),
        "deleted": deleted,
        "agents": agents,
        "skills": skills,
        "prompts": prompts,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        type=Path,
        help=(
            "Codex home/config path. Use ~/.codex for the standard Codex layout, or the "
            "JetBrains aia/codex cache root for the JetBrains layout."
        ),
    )
    parser.add_argument(
        "--layout",
        choices=("auto", "home", "jetbrains"),
        default="auto",
        help="destination layout; auto uses jetbrains when <target>/.codex exists",
    )
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="delete previously installed Kitty-owned agents, skills, and prompts before copying",
    )
    args = parser.parse_args(argv)

    result = install(args.target, layout_name=args.layout, delete_old=args.delete_old)
    print("Installed Codex assets:")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
