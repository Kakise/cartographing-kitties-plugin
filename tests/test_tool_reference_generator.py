from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

from cartograph.server.tools import analysis

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = REPO_ROOT / "plugins" / "kitty" / "skills" / "kitty" / "references"


def test_tool_reference_generator_check_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_tool_reference.py", "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_tool_reference_is_split_by_family() -> None:
    tool_reference_dir = REFERENCE_DIR / "tool-reference"
    family_files = {path.name for path in tool_reference_dir.glob("*.md")}

    assert family_files == {
        "analysis.md",
        "annotate.md",
        "index.md",
        "memory.md",
        "query.md",
        "reactive.md",
    }
    assert not (REFERENCE_DIR / "tool-reference.md").exists()


def test_generated_tool_reference_includes_new_response_controls() -> None:
    query_reference = (REFERENCE_DIR / "tool-reference" / "query.md").read_text()
    analysis_reference = (REFERENCE_DIR / "tool-reference" / "analysis.md").read_text()

    assert "`response_shape`" in query_reference
    assert "`token_budget`" in query_reference
    assert "`cursor`" in analysis_reference
    assert "`limit`" in analysis_reference


def test_analysis_tools_share_traversal_helper() -> None:
    assert hasattr(analysis, "_traverse")
    assert "return _traverse(" in inspect.getsource(analysis.find_dependencies)
    assert "return _traverse(" in inspect.getsource(analysis.find_dependents)
