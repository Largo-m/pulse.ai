"""The domain and the engine are type-checked as `mypy --strict`, with no `Any` in their code.

`mypy` enforces it on every run; this test keeps the override from being
weakened or dropped, which `mypy` itself would accept without a word.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRICT_PACKAGES = ("pulse.domain", "pulse.orchestrator")
STRICT_MODULES = {module for package in STRICT_PACKAGES for module in (package, f"{package}.*")}
# `--strict` flags that can be set per module, plus the three that ban written `Any`.
REQUIRED_FLAGS = {
    "disallow_any_generics",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_defs",
    "disallow_incomplete_defs",
    "check_untyped_defs",
    "disallow_untyped_decorators",
    "warn_return_any",
    "no_implicit_reexport",
    "strict_equality",
    "extra_checks",
    "disallow_any_explicit",
    "disallow_any_unimported",
    "disallow_any_decorated",
}


def _strict_override() -> dict[str, object]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    for override in config["tool"]["mypy"]["overrides"]:
        if set(override["module"]) == STRICT_MODULES:
            return dict(override)
    return {}


def test_the_domain_and_the_engine_are_checked_strictly_with_no_any() -> None:
    override = _strict_override()

    assert {flag for flag in REQUIRED_FLAGS if override.get(flag) is not True} == set()


def test_no_error_code_is_switched_off_for_a_strict_package() -> None:
    """A baseline entry would turn the strict override back into a suggestion."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    relaxed = [
        override["module"]
        for override in config["tool"]["mypy"]["overrides"]
        if "disable_error_code" in override
        and any(module.startswith(STRICT_PACKAGES) for module in override["module"])
    ]

    assert relaxed == []
