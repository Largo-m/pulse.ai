"""Agent runtime registry.

A *runtime* is the backend that runs a Pulse agent: which binary, how to speak
ACP with it, how to check the environment and how to apply mode and model.
Adding a new agent means one module here plus an entry in `RUNTIMES`.
"""

from __future__ import annotations

from pathlib import Path

from pulse.runtimes.base import AgentRuntime, RuntimeCheck
from pulse.runtimes.claude import ClaudeRuntime
from pulse.runtimes.cursor import CursorRuntime

DEFAULT_RUNTIME_ID = "cursor"

RUNTIMES: dict[str, AgentRuntime] = {
    runtime.id: runtime for runtime in (CursorRuntime(), ClaudeRuntime())
}


def runtime_ids() -> list[str]:
    return list(RUNTIMES)


def all_runtimes() -> list[AgentRuntime]:
    return list(RUNTIMES.values())


class UnknownRuntime(LookupError):
    """A runtime id missing from `RUNTIMES`."""


def get_runtime(name: str) -> AgentRuntime:
    """Runtime by id. An unknown id does not exist: falling back would start another CLI."""
    runtime = find_runtime(name)
    if runtime is None:
        raise UnknownRuntime(f"unknown runtime: {name!r}")
    return runtime


def find_runtime(name: str | None) -> AgentRuntime | None:
    if not name:
        return None
    return RUNTIMES.get(name.strip().lower())


def runtime_for_command(command: list[str] | tuple[str, ...]) -> AgentRuntime:
    """Runtime whose ACP command matches `command` (for already configured sessions)."""
    parts = [_without_version(str(item)) for item in command]
    for runtime in RUNTIMES.values():
        if [_without_version(item) for item in runtime.acp_command] == parts:
            return runtime
    executable = Path(parts[0]).name if parts else ""
    for runtime in RUNTIMES.values():
        if executable == runtime.binary:
            return runtime
    return RUNTIMES[DEFAULT_RUNTIME_ID]


def _without_version(part: str) -> str:
    """Treat `@scope/package@1.2.3` and `@scope/package` as the same ACP command.

    Keeps config saved before the version pin matching.
    """
    name, at, _version = part.rpartition("@")
    return name if at and name else part


__all__ = [
    "DEFAULT_RUNTIME_ID",
    "RUNTIMES",
    "AgentRuntime",
    "RuntimeCheck",
    "UnknownRuntime",
    "all_runtimes",
    "find_runtime",
    "get_runtime",
    "runtime_for_command",
    "runtime_ids",
]
