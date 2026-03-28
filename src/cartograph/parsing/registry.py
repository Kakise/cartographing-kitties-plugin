"""Tree-sitter parser registry with per-language caching."""

from __future__ import annotations

from pathlib import Path

import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Parser, Tree

# Extension -> language name mapping
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
}


def _get_language(lang_name: str) -> Language:
    """Return the tree-sitter Language object for a language name."""
    if lang_name == "python":
        return Language(tree_sitter_python.language())
    elif lang_name == "typescript":
        return Language(tree_sitter_typescript.language_typescript())
    elif lang_name == "tsx":
        return Language(tree_sitter_typescript.language_tsx())
    elif lang_name == "javascript":
        return Language(tree_sitter_javascript.language())
    else:
        raise ValueError(f"Unsupported language: {lang_name}")


class ParserRegistry:
    """Registry that maps file extensions to tree-sitter parsers and caches them."""

    def __init__(self) -> None:
        self._parsers: dict[str, tuple[Parser, Language]] = {}

    def get_parser(self, file_path: str | Path) -> tuple[Parser, Language]:
        """Return a (Parser, Language) tuple for the given file path.

        Parsers are cached per language so they can be reused across files.
        """
        path = Path(file_path)
        ext = path.suffix
        lang_name = EXTENSION_MAP.get(ext)
        if lang_name is None:
            raise ValueError(f"Unsupported file extension: {ext}")

        if lang_name not in self._parsers:
            language = _get_language(lang_name)
            parser = Parser(language)
            self._parsers[lang_name] = (parser, language)

        return self._parsers[lang_name]

    def parse_file(self, file_path: str | Path) -> Tree:
        """Read and parse a file, returning the tree-sitter Tree."""
        path = Path(file_path)
        source = path.read_bytes()
        parser, _language = self.get_parser(path)
        return parser.parse(source)

    @staticmethod
    def language_for_file(file_path: str | Path) -> str | None:
        """Return the language name for a file path, or None if unsupported."""
        ext = Path(file_path).suffix
        return EXTENSION_MAP.get(ext)
