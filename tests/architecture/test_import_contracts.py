"""AGENTS.md §2.1: the layering rules, checked by import-linter.

The contracts live in `[tool.importlinter]` of `pyproject.toml`; this test runs
them in `pytest` so a broken layer fails the same suite as a broken behavior.
"""

from __future__ import annotations

from pathlib import Path

from importlinter.api import read_configuration
from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports

PYPROJECT = str(Path(__file__).resolve().parents[2] / "pyproject.toml")
REQUIRED_CONTRACTS = {
    "TUI and client are thin: they never import the engine",
    "Domain stays free of UI and web frameworks",
    "Only store/db.py loads the factory seed",
}


def test_every_import_contract_is_kept() -> None:
    """The TUI never runs the engine, the domain never sees a UI, only the store loads the seed.

    On failure, `lint-imports` prints the offending import chain.
    """
    assert lint_imports(config_filename=PYPROJECT, no_cache=True) == EXIT_STATUS_SUCCESS


def test_no_layering_contract_was_dropped_from_the_config() -> None:
    """Guards the guard: deleting a contract would keep the test above green forever."""
    contracts = read_configuration(PYPROJECT)["contracts_options"]

    assert REQUIRED_CONTRACTS <= {contract["name"] for contract in contracts}
