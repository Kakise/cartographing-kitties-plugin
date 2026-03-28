"""Smoke tests: verify package imports and tree-sitter grammars load."""


def test_cartograph_imports():
    """Package imports successfully."""
    import cartograph

    assert cartograph.__version__


def test_tree_sitter_python_grammar():
    """Python grammar loads and can parse code."""
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    language = Language(tspython.language())
    parser = Parser(language)
    tree = parser.parse(b"def foo(): pass")
    assert tree.root_node.type == "module"


def test_tree_sitter_typescript_grammar():
    """TypeScript grammar loads and can parse code."""
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser

    language = Language(tstypescript.language_typescript())
    parser = Parser(language)
    tree = parser.parse(b"function foo(): void {}")
    assert tree.root_node.type == "program"


def test_tree_sitter_tsx_grammar():
    """TSX grammar loads."""
    import tree_sitter_typescript as tstypescript
    from tree_sitter import Language, Parser

    language = Language(tstypescript.language_tsx())
    parser = Parser(language)
    tree = parser.parse(b"const App = () => <div />;")
    assert tree.root_node.type == "program"


def test_tree_sitter_javascript_grammar():
    """JavaScript grammar loads and can parse code."""
    import tree_sitter_javascript as tsjavascript
    from tree_sitter import Language, Parser

    language = Language(tsjavascript.language())
    parser = Parser(language)
    tree = parser.parse(b"function foo() {}")
    assert tree.root_node.type == "program"
