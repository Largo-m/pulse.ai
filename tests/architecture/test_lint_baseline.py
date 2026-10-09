"""AGENTS.md §5.2: the lint and type gates have no baseline exceptions.

Phase 7 paid the baseline down to zero. A per-file ignore or a disabled mypy
error code is debt that hides new findings in the same file, so the config may
only hold the policy entries below; anything else is fixed in the code or
suppressed on its line with a reason (§4.5).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

# Policy, not debt: asserts are how pytest tests, and these modules exist to
# write to the terminal.
POLICY_IGNORES = {
    "tests/**": ["S101", "ANN"],
    "pulse/cli/daemon_command.py": ["T201"],
    "pulse/cli/main.py": ["T201"],
    "pulse/config/commands.py": ["T201"],
    "pulse/doctor/report.py": ["T201"],
}
MAX_COMPLEXITY = 10


def _tool() -> dict[str, Any]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]


def _ruff_lint() -> dict[str, Any]:
    return _tool()["ruff"]["lint"]


def test_ruff_ignores_only_the_policy_entries() -> None:
    """A new per-file ignore would silence a whole rule for a whole file."""
    assert _ruff_lint()["per-file-ignores"] == POLICY_IGNORES


def test_complexity_is_checked_by_ruff_and_capped() -> None:
    """C901 blocks the merge through `ruff check`, at the agreed ceiling."""
    lint = _ruff_lint()
    assert "C90" in lint["select"]
    assert lint["mccabe"] == {"max-complexity": MAX_COMPLEXITY}


def test_mypy_disables_no_error_code() -> None:
    """A disabled error code lets every new error of that kind into the module."""
    overrides = _tool()["mypy"].get("overrides", [])
    assert [o["module"] for o in overrides if "disable_error_code" in o] == []
