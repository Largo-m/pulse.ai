"""As runs que o daemon tem vivas, para as telas que oferecem voltar a elas.

A Home e o Histórico precisam da mesma resposta — "o que está rodando agora?" —
e nenhuma das duas pode quebrar porque o daemon não respondeu: sem engine não há
run viva, e a tela simplesmente não oferece reabrir nenhuma.
"""

from __future__ import annotations

import time
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


def awaiting_runs() -> list[dict[str, Any]]:
    """As que pararam esperando o usuário — o que a Home anuncia.

    Mais antiga primeiro: quem está esperando há mais tempo é quem tem mais
    chance de estar segurando o trabalho de alguém.
    """
    waiting = [run for run in active_runs() if run.get("awaiting_prompt")]
    waiting.sort(key=lambda run: run.get("awaiting_since") or run.get("started_at") or 0.0)
    return waiting


def waiting_for(run: dict[str, Any], *, now: float | None = None) -> str:
    """Há quanto tempo esta run espera resposta. Vazio se não está esperando.

    Aqui o texto é grosso (`3min`), e não o `MM:SS` do cronômetro da sidebar:
    este número não é precisão, é urgência — quem lê quer saber se deixou
    alguém esperando cinco minutos ou a tarde inteira, e o segundo exato só
    atrapalharia a leitura de uma linha de aviso.
    """
    since = run.get("awaiting_since")
    if not since:
        return ""
    elapsed = (time.time() if now is None else now) - float(since)
    if elapsed < 0:
        return ""
    if elapsed < 60:
        return f"{int(elapsed)}s"
    if elapsed < 3600:
        return f"{int(elapsed // 60)}min"
    hours, minutes = divmod(int(elapsed // 60), 60)
    return f"{hours}h{minutes:02d}"


def describe(run: dict[str, Any]) -> str:
    """Uma linha de menu: o loop, onde está e se está esperando alguém."""
    label = str(run.get("workflow_label") or run.get("workflow_id") or "Run")
    parts = [label]
    step = str(run.get("current_step_label") or "").strip()
    if step:
        parts.append(step)
    if run.get("awaiting_prompt"):
        held = waiting_for(run)
        parts.append(f"precisa de você há {held}" if held else "precisa de você")
    else:
        parts.append("executando")
    return " · ".join(parts)
