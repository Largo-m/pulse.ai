"""AGENTS.md §4.3: no file crosses the line limit.

A file past the limit holds more than one reason to change; extract a focused
module (as `loops.py` and `fanout.py` were) instead of adding to it.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("pulse", "tests")
LINE_LIMIT = 1000  # Phase 8 lowers it to 700.
# Files over the limit when it landed, each capped at its current size. Entries
# only shrink or leave this map: split the file, then lower or delete its line.
OVERSIZED = {
    "tests/orchestrator/test_engine_steps.py": 1405,
}


def _line_counts() -> dict[str, int]:
    return {
        path.relative_to(ROOT).as_posix(): len(path.read_text(encoding="utf-8").splitlines())
        for directory in SOURCE_DIRS
        for path in (ROOT / directory).rglob("*.py")
        if "__pycache__" not in path.parts
    }


def test_no_file_crosses_line_limit() -> None:
    too_long = {
        path: lines
        for path, lines in _line_counts().items()
        if lines > LINE_LIMIT and path not in OVERSIZED
    }

    assert too_long == {}


def test_an_oversized_file_is_capped_at_its_current_size() -> None:
    """The exception is a debt to pay, not a licence to keep adding to the file.

    A cap above the current size would let a trimmed file grow back unnoticed,
    so shrinking the file means lowering its cap in the same change.
    """
    counts = _line_counts()
    drifted = {path: counts.get(path) for path, cap in OVERSIZED.items() if counts.get(path) != cap}

    assert drifted == {}


def test_the_exception_list_only_shrinks() -> None:
    """An entry that is back under the limit, or gone, must leave the map so it can't regrow."""
    counts = _line_counts()
    stale = [path for path in OVERSIZED if counts.get(path, 0) <= LINE_LIMIT]

    assert stale == []
