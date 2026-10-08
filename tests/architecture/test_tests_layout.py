"""`tests/` mirrors `pulse/`: the tests of a package are found by its name.

A test dropped at the root, or a package with nowhere to put its tests, is how
the suite drifts back into a flat list nobody can navigate.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "pulse"
TESTS = ROOT / "tests"
INFRA = "infra"
# Adapters share one test folder; the daemon is tested through the API it serves.
FOLDED = {
    "acp": INFRA,
    "runtimes": INFRA,
    "store": INFRA,
    "vcs": INFRA,
    "mcp": INFRA,
    "daemon": "api",
}
# Folders that test the repo as a whole rather than one package.
CROSS_CUTTING = {"architecture"}


def mirror_folder(package: str) -> str:
    return FOLDED.get(package, package)


def _packages() -> set[str]:
    return {path.name for path in PACKAGE.iterdir() if (path / "__init__.py").is_file()}


def _test_folders() -> set[str]:
    return {path.name for path in TESTS.iterdir() if path.is_dir() and path.name != "__pycache__"}


def test_every_package_has_a_test_folder() -> None:
    missing = sorted(
        package for package in _packages() if not (TESTS / mirror_folder(package)).is_dir()
    )

    assert missing == []


def test_every_test_folder_belongs_to_a_package() -> None:
    """A folder named after a package that moved would hide its tests from the mirror."""
    expected = {mirror_folder(package) for package in _packages()} | CROSS_CUTTING

    assert sorted(_test_folders() - expected) == []


def test_every_test_folder_holds_tests() -> None:
    empty = sorted(
        folder for folder in _test_folders() if not any((TESTS / folder).glob("test_*.py"))
    )

    assert empty == []


def test_no_test_lives_at_the_root_of_tests() -> None:
    assert sorted(path.name for path in TESTS.glob("test_*.py")) == []


def test_adapters_fold_into_infra_and_the_rest_keep_their_name() -> None:
    """Guards the guard: a mapping that sent everything to one folder would pass forever."""
    assert mirror_folder("store") == INFRA
    assert mirror_folder("daemon") == "api"
    assert mirror_folder("domain") == "domain"
