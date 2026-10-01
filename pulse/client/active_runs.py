"""As runs que o daemon tem vivas, para as telas que oferecem voltar a elas.

A Home e o Histórico precisam da mesma resposta — "o que está rodando agora?" —
e nenhuma das duas pode quebrar porque o daemon não respondeu: sem engine não há
run viva, e a tela simplesmente não oferece reabrir nenhuma.
"""

from __future__ import annotations

from typing import Any

from pulse.client.engine_client import EngineClient


#: A TUI consulta isto de dentro do laço de eventos: melhor não oferecer a run
#: do que travar a tela esperando um daemon que já morreu.
_TIMEOUT = 2.0


def list_runs() -> list[dict[str, Any]]:
    """Tudo que o daemon guarda em memória, ativo ou recém-encerrado."""
    client = EngineClient(timeout=_TIMEOUT)
    try:
        return client.list_runs()
    except Exception:
        return []
    finally:
        client.close()


def active_runs() -> list[dict[str, Any]]:
    """Só o que ainda está rodando — a lista que vira item de menu."""
    return [run for run in list_runs() if run.get("active")]


def active_run_ids() -> set[str]:
    return {str(run["id"]) for run in active_runs() if run.get("id")}


def describe(run: dict[str, Any]) -> str:
    """Uma linha de menu: o loop, onde está e se está esperando alguém."""
    label = str(run.get("workflow_label") or run.get("workflow_id") or "Run")
    parts = [label]
    step = str(run.get("current_step_label") or "").strip()
    if step:
        parts.append(step)
    parts.append(
        "aguardando sua resposta" if run.get("awaiting_prompt") else "executando"
    )
    return " · ".join(parts)
