"""The domain, the engine and the reply parsers are `mypy --strict`, with no `Any`.

`mypy` enforces it on every run; this test keeps the override from being
weakened or dropped, which `mypy` itself would accept without a word.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRICT_PACKAGES = ("pulse.domain", "pulse.orchestrator", "pulse.replies")
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


def _overrides() -> list[dict[str, object]]:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return list(config["tool"]["mypy"]["overrides"])


def _modules(override: dict[str, object]) -> set[str]:
    module = override["module"]
    return {module} if isinstance(module, str) else set(module)


def _is_strict(module: str) -> bool:
    return any(module == package or module.startswith(f"{package}.") for package in STRICT_PACKAGES)


def _relaxed_modules(overrides: list[dict[str, object]]) -> set[str]:
    """Strict modules another override reaches: mypy lets the narrower section win."""
    return {
        module
        for override in overrides
        if _modules(override) != STRICT_MODULES
        for module in _modules(override)
        if _is_strict(module)
    }


def _strict_override(overrides: list[dict[str, object]]) -> dict[str, object]:
    return next((o for o in overrides if _modules(o) == STRICT_MODULES), {})


def test_the_domain_the_engine_and_the_replies_are_checked_strictly_with_no_any() -> None:
    override = _strict_override(_overrides())

    assert {flag for flag in REQUIRED_FLAGS if override.get(flag) is not True} == set()


def test_the_strict_override_holds_only_the_strict_flags() -> None:
    """`ignore_errors` or `disable_error_code` there would turn it into a suggestion."""
    override = _strict_override(_overrides())

    assert set(override) - {"module"} == REQUIRED_FLAGS


def test_no_other_override_reaches_a_strict_module() -> None:
    """A section for `pulse.domain.run` alone would switch its flags back off."""
    assert _relaxed_modules(_overrides()) == set()


def test_the_guard_sees_a_narrower_override_of_a_strict_module() -> None:
    """Probe: the guard is blind if it misses the override that would weaken it."""
    strict = {"module": sorted(STRICT_MODULES), **dict.fromkeys(REQUIRED_FLAGS, True)}
    narrower = {"module": "pulse.domain.run", "disallow_any_explicit": False}
    elsewhere = {"module": ["pulse.domainless", "pulse.tui.*"], "ignore_errors": True}

    assert _relaxed_modules([strict, narrower, elsewhere]) == {"pulse.domain.run"}
