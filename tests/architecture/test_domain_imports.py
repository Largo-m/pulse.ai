"""Domain types are imported from `pulse.domain`, never through a module that uses them.

`run_store.RunRecord` made the store look like the owner of the aggregate: the
engine depended on persistence to name a domain type, and the store could not
drop an import without breaking callers. A name a module got from the domain
is not part of that module's API.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIRS = ("pulse", "tests")
DOMAIN = "pulse.domain"


def _module_name(path: Path) -> str:
    parts = path.relative_to(ROOT).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _module_path(module: str) -> Path | None:
    base = ROOT.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def _is_domain(module: str) -> bool:
    return module == DOMAIN or module.startswith(f"{DOMAIN}.")


def _names_taken_from_domain(module: str) -> frozenset[str]:
    """Names `module` binds by importing them from the domain."""
    path = _module_path(module)
    if path is None:
        return frozenset()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return frozenset(
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and _is_domain(node.module or "")
        for alias in node.names
    )


def _sources() -> Iterator[Path]:
    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*.py"):
            if "__pycache__" not in path.parts:
                yield path


def _module_aliases(tree: ast.AST) -> dict[str, str]:
    """Local name -> Pulse module, for `import pulse.x as a` and `from pulse import x`."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname and alias.name.startswith("pulse."):
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pulse"):
            for alias in node.names:
                submodule = f"{node.module}.{alias.name}"
                if _module_path(submodule) is not None:
                    aliases[alias.asname or alias.name] = submodule
    return aliases


def _violations(where: str, text: str) -> Iterator[str]:
    tree = ast.parse(text)
    aliases = _module_aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            source = node.module or ""
            if not source.startswith("pulse") or _is_domain(source):
                continue
            borrowed = _names_taken_from_domain(source)
            for alias in node.names:
                if alias.name in borrowed:
                    yield f"{where}:{node.lineno} from {source} import {alias.name}"
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            source = aliases.get(node.value.id, "")
            if source and not _is_domain(source) and node.attr in _names_taken_from_domain(source):
                yield f"{where}:{node.lineno} {node.value.id}.{node.attr}"


def test_domain_names_are_imported_from_the_domain() -> None:
    violations = [
        line
        for path in _sources()
        if not _is_domain(_module_name(path))
        for line in _violations(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8"))
    ]

    assert violations == []


def test_the_check_catches_a_domain_name_reached_through_the_store() -> None:
    """Guards the oracle: the store does import `RunRecord`, so both spellings must be caught."""
    probe = (
        "from pulse.store import runs as run_store\n"
        "from pulse.store.runs import RunStatus, create_run\n"
        "record: run_store.RunRecord\n"
        "run_store.save\n"
    )

    assert list(_violations("probe.py", probe)) == [
        "probe.py:2 from pulse.store.runs import RunStatus",
        "probe.py:3 run_store.RunRecord",
    ]
