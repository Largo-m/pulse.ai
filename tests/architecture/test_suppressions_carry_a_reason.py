"""AGENTS.md §4.5: every `# noqa` and `# type: ignore` says why.

A naked suppression hides the next finding on the same line, and the reader
cannot tell a reviewed exception from a silenced one. The reason sits on the
same line or in a comment just above the statement it covers.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNED = ("pulse", "tests", "scripts")
DIRECTIVE = re.compile(
    r"#\s*(?:noqa(?::\s*[A-Z]+\d+(?:\s*,\s*[A-Z]+\d+)*)?|type:\s*ignore(?:\[[^\]]*\])?)"
)
# A multi-line call carries its reason above the call, a few lines up.
REASON_WINDOW = 5


def _naked(lines: list[str]) -> list[int]:
    naked = []
    for index, line in enumerate(lines):
        directive = DIRECTIVE.search(line)
        if directive is None or line[directive.end() :].strip(" -#:"):
            continue
        above = lines[max(0, index - REASON_WINDOW) : index]
        if not any(previous.strip().startswith("#") for previous in above):
            naked.append(index + 1)
    return naked


def test_a_suppression_with_its_reason_passes() -> None:
    assert _naked(["x = f()  # noqa: S603 - fixed argv"]) == []
    assert _naked(["# argv is a constant", "run(", "    argv,  # noqa: S603", ")"]) == []


def test_a_naked_suppression_is_caught() -> None:
    assert _naked(["x = f()  # noqa: S603", "y = g()  # type: ignore[assignment]"]) == [1, 2]


def test_no_suppression_in_the_repo_is_naked() -> None:
    found = [
        f"{path.relative_to(ROOT)}:{number}"
        for root in SCANNED
        for path in sorted((ROOT / root).rglob("*.py"))
        for number in _naked(path.read_text(encoding="utf-8").splitlines())
    ]

    assert found == []
