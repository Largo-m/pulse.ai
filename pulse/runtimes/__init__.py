"""Registry de runtimes de agente.

Um *runtime* é o backend que executa um Pulse agent: qual binário roda, como se
fala ACP com ele, como se checa o ambiente e como se aplica modo e modelo.
Adicionar um agente novo = um módulo aqui + uma entrada em `RUNTIMES`.
"""

from __future__ import annotations

from pulse.runtimes.base import AgentRuntime, ModelRequest, RuntimeCheck
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


def get_runtime(name: str | None) -> AgentRuntime:
    """Runtime pelo id; cai no default para `default`/desconhecido."""
    if name:
        runtime = RUNTIMES.get(name.strip().lower())
        if runtime is not None:
            return runtime
    return RUNTIMES[DEFAULT_RUNTIME_ID]


def find_runtime(name: str | None) -> AgentRuntime | None:
    if not name:
        return None
    return RUNTIMES.get(name.strip().lower())


def runtime_for_command(command: list[str] | tuple[str, ...]) -> AgentRuntime:
    """Runtime cujo comando ACP bate com `command` (para sessões já configuradas)."""
    parts = [str(item) for item in command]
    for runtime in RUNTIMES.values():
        if runtime.acp_command == parts:
            return runtime
    for runtime in RUNTIMES.values():
        if parts and runtime.binary in parts[0]:
            return runtime
    return RUNTIMES[DEFAULT_RUNTIME_ID]


__all__ = [
    "DEFAULT_RUNTIME_ID",
    "RUNTIMES",
    "AgentRuntime",
    "ModelRequest",
    "RuntimeCheck",
    "all_runtimes",
    "find_runtime",
    "get_runtime",
    "runtime_for_command",
    "runtime_ids",
]
