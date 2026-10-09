"""AGENTS.md §2.1: the layering rules, checked by import-linter.

The contracts live in `[tool.importlinter]` of `pyproject.toml`; this test runs
them in `pytest` so a broken layer fails the same suite as a broken behavior.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from importlinter.api import read_configuration
from importlinter.cli import EXIT_STATUS_SUCCESS, lint_imports

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = str(ROOT / "pyproject.toml")
TUI_THROUGH_DAEMON = "The TUI reaches persistence, config and runtimes only through the daemon"
ADAPTERS_APART = "Adapters depend on the domain, not on each other"
HISTORY_DATABASE = "History reaches the database only through its catalog and session log"
REQUIRED_CONTRACTS = {
    "TUI and client are thin: they never import the engine",
    "Domain stays free of UI and web frameworks",
    "Domain values and reply parsing need nothing else from Pulse",
    "The engine reaches infrastructure only through ports",
    "Only the CLI opens the TUI",
    "Only store/db.py loads the factory seed",
    TUI_THROUGH_DAEMON,
    ADAPTERS_APART,
    HISTORY_DATABASE,
    "Engine wording is the engine's own",
    "Run log wording belongs to history and the screens that redraw it",
    "Question wording belongs to the reply builders and the screens that ask",
}
# import-linter fails on a baseline entry that stops matching, but not on a new
# one; these ceilings make the baselines shrink-only, and a contract not listed
# has a ceiling of 0. Lower them as debt is paid.
# The TUI's one entry is the shared `~/.pulse` layout, and history's six are the
# catalog's and session log's own edges to the database: rules rather than debt.
BASELINE_CEILING = {
    "TUI and client are thin: they never import the engine": 0,
    TUI_THROUGH_DAEMON: 1,
    ADAPTERS_APART: 0,
    HISTORY_DATABASE: 6,
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


@pytest.fixture
def loggers_left_enabled() -> Iterator[None]:
    """`lint_imports` calls `dictConfig`, which disables every logger created before it.

    Without restoring them, a later test that reads `caplog` sees no records,
    depending on the random order.
    """
    loggers = [
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    ]
    disabled = {logger: logger.disabled for logger in loggers}
    yield
    for logger, flag in disabled.items():
        logger.disabled = flag


@pytest.mark.usefixtures("loggers_left_enabled")
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


@pytest.mark.parametrize("name", sorted(_contracts()))
def test_a_contract_baseline_never_grows(name: str) -> None:
    """A new layering shortcut must be fixed, not appended to `ignore_imports`."""
    assert len(_contracts()[name].get("ignore_imports", [])) <= BASELINE_CEILING.get(name, 0)


def test_every_baseline_ceiling_names_a_contract() -> None:
    """A ceiling left behind by a renamed contract would cap nothing."""
    assert set(BASELINE_CEILING) <= set(_contracts())


def test_the_domain_holds_no_screen_copy_module():
    """Screen text once lived in `domain/ui_text.py` because every layer may import
    the domain: a workaround of the layering, not a home (docs/adr/0004)."""
    copy_like = {"ui_text", "strings", "wording", "copy", "messages", "texts"}

    modules = {path.stem for path in (ROOT / "pulse" / "domain").glob("*.py")}

    assert modules.isdisjoint(copy_like)
