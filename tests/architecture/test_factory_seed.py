"""AGENTS.md §2.2 invariant 1: domain content lives only in the factory seed.

The engine must stay unaware of any specific workflow; a playbook file or a
workflow name leaking into the package is how that awareness starts.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2] / "pulse"
FACTORY = PACKAGE / "store" / "factory"
DOMAIN_VOCABULARY = re.compile(
    r"\bprd\b|techspec|new-issue|quick-fix|setup-project|analyze-codebase|figma", re.IGNORECASE
)


def _package_files() -> list[Path]:
    return [
        path
        for path in PACKAGE.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and not path.is_relative_to(FACTORY)
    ]


def test_the_package_ships_no_non_python_file_outside_the_factory() -> None:
    """Playbooks and other data belong to the seed, which only `store/db.py` loads."""
    strays = [str(path.relative_to(PACKAGE)) for path in _package_files() if path.suffix != ".py"]

    assert strays == []


def test_no_module_outside_the_factory_names_a_seeded_workflow() -> None:
    """Behavior comes from definition columns, never from knowing a workflow by name."""
    leaks = [
        f"{path.relative_to(PACKAGE)}:{number}"
        for path in _package_files()
        if path.suffix == ".py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if DOMAIN_VOCABULARY.search(line)
    ]

    assert leaks == []


def test_the_vocabulary_check_recognises_a_leak() -> None:
    """Guards the guard: a regex that matches nothing would pass the test above forever."""
    assert DOMAIN_VOCABULARY.search('if workflow_id == "quick-fix":')
    assert DOMAIN_VOCABULARY.search("write the PRD first")
    assert DOMAIN_VOCABULARY.search("#### Link do Figma:")
    assert not DOMAIN_VOCABULARY.search("prdx = approved")


def test_the_wheel_ships_every_file_of_the_factory_seed() -> None:
    """An editable install reads the seed from the checkout, so a file left out of
    `package-data` only breaks an installed Pulse, on its first database open."""
    pyproject = tomllib.loads((PACKAGE.parent / "pyproject.toml").read_text(encoding="utf-8"))
    patterns = pyproject["tool"]["setuptools"]["package-data"]["pulse.store.factory"]
    shipped = {path for pattern in patterns for path in FACTORY.glob(pattern)}
    seed = {
        path
        for path in FACTORY.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    }

    assert sorted(str(path.relative_to(FACTORY)) for path in seed - shipped) == []
