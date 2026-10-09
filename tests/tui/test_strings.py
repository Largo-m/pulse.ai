from __future__ import annotations

import ast
from pathlib import Path

import pulse.tui

_TUI_ROOT = Path(pulse.tui.__file__).parent
_STRINGS_MODULE = _TUI_ROOT / "strings.py"
_PORTUGUESE_LETTERS = frozenset("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ")


def _docstring_nodes(tree: ast.Module) -> set[int]:
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, owners) or not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            found.add(id(first.value))
    return found


def _portuguese_literals(source: str) -> list[tuple[int, str]]:
    """(line, text) of every string literal with a Portuguese letter, docstrings aside."""
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    return sorted(
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and _PORTUGUESE_LETTERS.intersection(node.value)
    )


def test_tui_copy_lives_only_in_the_strings_module():
    """Screens show Portuguese, code stays English: copy outside `strings.py` is a leak.

    A Portuguese literal in a screen or widget means UI text escaped the one
    module where wording is reviewed and changed, and is the first sign of
    copy drifting between screens.
    """
    leaks = [
        f"{path.relative_to(_TUI_ROOT)}:{line}: {text!r}"
        for path in sorted(_TUI_ROOT.rglob("*.py"))
        if path != _STRINGS_MODULE
        for line, text in _portuguese_literals(path.read_text(encoding="utf-8"))
    ]

    assert leaks == []


def test_the_leak_detector_flags_literals_and_f_strings_but_not_docstrings():
    """The guard above is only as good as its detector: check both directions."""
    source = '''
def screen():
    """Docstring with ação is documentation, not copy."""
    label = "Histórico"
    notice = f"Run {name} concluída"
    return "plain ascii"
'''

    assert _portuguese_literals(source) == [(4, "Histórico"), (5, " concluída")]
