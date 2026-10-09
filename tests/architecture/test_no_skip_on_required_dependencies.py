"""AGENTS.md §5.1: no skip to keep CI green.

`pytest.importorskip` of a package Pulse requires turns a broken install into
whole modules that skip in silence: the suite stays green while it tests
nothing. A required dependency is imported plainly, so a failure is an error.
"""

from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
_NAME = re.compile(r"[A-Za-z0-9._-]+")


def _required() -> set[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    names = (_NAME.match(spec) for spec in project["dependencies"])
    return {match.group(0).lower().replace("-", "_") for match in names if match}


def _skipped_imports(source: str) -> list[tuple[int, str]]:
    return [
        (node.lineno, node.args[0].value)
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "importorskip"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ]


def test_no_test_skips_on_a_required_dependency() -> None:
    required = _required()
    offenders = [
        f"{path.relative_to(TESTS)}:{line} {module}"
        for path in sorted(TESTS.rglob("*.py"))
        if "__pycache__" not in path.parts
        for line, module in _skipped_imports(path.read_text(encoding="utf-8"))
        if module.split(".")[0] in required
    ]

    assert offenders == []


def test_the_check_reads_the_skip_and_the_dependencies() -> None:
    """Guards the guard: a detector that finds nothing would pass forever."""
    assert _skipped_imports('import pytest\npytest.importorskip("textual")\n') == [(2, "textual")]
    assert _skipped_imports("import textual\n") == []
    assert {"textual", "fastapi"} <= _required()
