"""AGENTS.md §5.1: no `sleep` for synchronization in tests.

A sleep guesses how long another thread needs; on a loaded CI runner the guess
is wrong and the test flakes. Wait on what the code signals instead (an Event,
a bus event, `poll(timeout=...)`), or drive time with a simulated clock.
"""

from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
SLEEPS = {"sleep", "asyncio.sleep", "time.sleep"}


def _called_name(node: ast.Call) -> str:
    target = node.func
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
        return f"{target.value.id}.{target.attr}"
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _sleeps(source: str) -> list[int]:
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and _called_name(node) in SLEEPS
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
