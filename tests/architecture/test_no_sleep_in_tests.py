"""AGENTS.md §5.1: no `sleep` for synchronization in tests.

A sleep guesses how long another thread needs; on a loaded CI runner the guess
is wrong and the test flakes. Wait on what the code signals instead (an Event,
a bus event, `poll(timeout=...)`), or drive time with a simulated clock.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
SLEEPING_MODULES = frozenset({"time", "asyncio", "anyio", "trio"})


def _sleep_names(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Names bound to a sleeping module, and names bound to its `sleep` itself."""
    modules = set(SLEEPING_MODULES)
    functions = {"sleep"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules |= {
                alias.asname or alias.name for alias in node.names if alias.name in SLEEPING_MODULES
            }
        elif isinstance(node, ast.ImportFrom) and node.module in SLEEPING_MODULES:
            functions |= {
                alias.asname or alias.name for alias in node.names if alias.name == "sleep"
            }
    return modules, functions


def _is_sleep(node: ast.Call, modules: set[str], functions: set[str]) -> bool:
    target = node.func
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        return target.attr == "sleep" and target.value.id in modules
    return isinstance(target, ast.Name) and target.id in functions


def _sleeps(source: str) -> list[int]:
    tree = ast.parse(source)
    modules, functions = _sleep_names(tree)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_sleep(node, modules, functions)
    ]


def test_no_test_sleeps():
    offenders = [
        f"{path.relative_to(TESTS)}:{line}"
        for path in sorted(TESTS.rglob("*.py"))
        if "__pycache__" not in path.parts
        for line in _sleeps(path.read_text(encoding="utf-8"))
    ]

    assert offenders == []


def test_the_check_recognises_a_sleep():
    """Guards the guard: a detector that finds nothing would pass forever."""
    assert _sleeps("import time\ntime.sleep(0.1)\n") == [2]
    assert _sleeps("from time import sleep\nsleep(1)\n") == [2]
    assert _sleeps("async def wait():\n    await asyncio.sleep(0)\n") == [2]
    assert _sleeps("# time.sleep(1) is banned\nevent.wait(1)\n") == []


def test_the_check_sees_through_aliases():
    """Renaming the module or the function is still a sleep."""
    assert _sleeps("import time as t\nt.sleep(1)\n") == [2]
    assert _sleeps("from time import sleep as pause\npause(1)\n") == [2]
    assert _sleeps("import anyio\nanyio.sleep(1)\n") == [2]
    assert _sleeps("clock.sleep(1)\n") == []
