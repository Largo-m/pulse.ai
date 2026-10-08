"""AGENTS.md §2.1: the layering rules, checked by import-linter.

The contracts live in `[tool.importlinter]` of `pyproject.toml`; this test runs
them in `pytest` so a broken layer fails the same suite as a broken behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from importlinter.api import read_configuration
from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = str(ROOT / "pyproject.toml")
REQUIRED_CONTRACTS = {
    "TUI and client are thin: they never import the engine",
    "Domain stays free of UI and web frameworks",
    "Domain values and reply parsing need nothing else from Pulse",
    "Only the CLI opens the TUI",
    "Only store/db.py loads the factory seed",
}
# Contracts that name every package but a few: import-linter has no wildcard
# for "the rest of pulse", so the list goes stale when a package is added.
EVERY_PACKAGE_BUT = {
    "Domain values and reply parsing need nothing else from Pulse": (
        "forbidden_modules",
        {"domain", "replies"},
    ),
    "Only the CLI opens the TUI": ("source_modules", {"cli", "tui"}),
}


def test_every_import_contract_is_kept() -> None:
    """The TUI never runs the engine, the domain sees neither UI nor I/O, only the store seeds.

    On failure, `lint-imports` prints the offending import chain.
    """
    assert lint_imports(config_filename=PYPROJECT, no_cache=True) == EXIT_STATUS_SUCCESS


def test_no_layering_contract_was_dropped_from_the_config() -> None:
    """Guards the guard: deleting a contract would keep the test above green forever."""
    assert REQUIRED_CONTRACTS <= set(_contracts())


def _contracts() -> dict[str, dict]:
    return {
        contract["name"]: contract
        for contract in read_configuration(PYPROJECT)["contracts_options"]
    }


@pytest.mark.parametrize(("name", "field_and_exempt"), sorted(EVERY_PACKAGE_BUT.items()))
def test_a_contract_over_the_rest_of_pulse_names_every_package(
    name: str, field_and_exempt: tuple[str, set[str]]
) -> None:
    """A package added later must be covered without anyone remembering to list it."""
    field, exempt = field_and_exempt
    packages = {
        path.name for path in (ROOT / "pulse").iterdir() if (path / "__init__.py").is_file()
    }

    listed = {module.removeprefix("pulse.") for module in _contracts()[name][field]}

    assert listed == packages - exempt
