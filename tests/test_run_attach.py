"""Sair do cockpit larga a tela, não a run.

A run vive no daemon; o cockpit é uma janela sobre ela. O que estes testes
guardam é a diferença entre as duas coisas: desanexar não cancela, não responde
pergunta nenhuma e não deixa thread presa, e voltar reencontra o relógio no
ponto em que estava.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pulse.client.run_session import DETACHED, EngineRunSession
from pulse.history.events import PhaseStatus
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.tui.adapters.prompt_bridge import PromptAbandoned, PromptBridge, PromptKind
from pulse.tui.hydrate import stamp_live_elapsed
from pulse.tui.state import CockpitState


class _BlockingClient:
    """Stream que não acaba — como o de uma run que ainda está trabalhando."""

    def __init__(self) -> None:
        self.cancelled: list[str] = []
        self.closed = False

    def stream_events(self, run_id: str, *, after: int = 0):
        from pulse.daemon.protocol import PING

        yield {"type": "phase.begin", "title": "Um"}
        while not self.closed:
            yield {"type": PING}
            time.sleep(0.01)

    def cancel_run(self, run_id: str):
        self.cancelled.append(run_id)
        return {"ok": True}

    def close(self) -> None:
        self.closed = True

    def answer_prompt(self, prompt_id: str, answer):
        return {"ok": True}


def test_detaching_leaves_the_run_alone():
    client = _BlockingClient()
    session = EngineRunSession(
        stream=MagicMock(),
        prompt_handler=MagicMock(),
        client=client,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.attach, "run-1")
        time.sleep(0.1)
        session.detach()
        assert future.result(timeout=5) == DETACHED
    # Largar a tela não é parar a run: ninguém pediu cancelamento.
    assert client.cancelled == []


def test_abandoning_the_bridge_frees_the_thread_without_answering():
    """A pergunta continua de pé no daemon; quem morre é a thread da tela."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        asking = pool.submit(
            bridge.request, PromptKind.TEXT, title="t", prompt="responde?"
        )
        deadline = time.monotonic() + 2
        while bridge.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        bridge.abandon()
        with pytest.raises(PromptAbandoned):
            asking.result(timeout=5)


def test_closing_the_bridge_still_cancels_what_is_open():
    """Run encerrada é outro caso: aí responder "cancelado" é a verdade."""
    bridge = PromptBridge()
    with ThreadPoolExecutor(max_workers=1) as pool:
        asking = pool.submit(bridge.request, PromptKind.TEXT, title="t", prompt="?")
        deadline = time.monotonic() + 2
        while bridge.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        bridge.close()
        assert asking.result(timeout=5) is None


def _seed_run(tmp_path: Path, *, run_id: str = "run-live") -> None:
    run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="x",
        steps=[
            StepRecord(step_id="one", position=1, label="Um", agent_id="tester"),
            StepRecord(step_id="two", position=2, label="Dois", agent_id="tester"),
        ],
    )


def test_the_clock_survives_leaving_and_coming_back(tmp_path: Path):
    """O replay remarca `phase.begin` agora; a hora de verdade é do banco."""
    _seed_run(tmp_path)
    now = datetime.now(UTC).replace(microsecond=0)
    run_store.save_step(
        "run-live",
        StepRecord(
            step_id="one",
            position=1,
            label="Um",
            agent_id="tester",
            status="done",
            started_at=(now - timedelta(seconds=90)).isoformat(),
            ended_at=(now - timedelta(seconds=60)).isoformat(),
        ),
    )
    run_store.save_step(
        "run-live",
        StepRecord(
            step_id="two",
            position=2,
            label="Dois",
            agent_id="tester",
            status="running",
            started_at=(now - timedelta(seconds=45)).isoformat(),
        ),
    )

    state = CockpitState()
    state.sync_phases([{"id": "one", "label": "Um"}, {"id": "two", "label": "Dois"}])
    state.phases[0].status = PhaseStatus.DONE
    # Como o replay deixa: o step em curso começando "agora".
    state.begin_phase("Dois")

    stamp_live_elapsed(state, "run-live")

    assert state.phases[0].elapsed_label() == "00:30"
    # O step vivo continua contando, mas de onde parou — não do zero.
    spent = time.monotonic() - state.phases[1].started_at
    assert 44 <= spent <= 50
    assert state.phases[1].ended_at is None


def test_history_puts_what_is_running_above_the_past(tmp_path: Path):
    """Em andamento é o único item da lista em que ainda dá para entrar."""
    from pulse.history.catalog import HistoryCatalog
    from pulse.history.models import HistoryStatus

    for run_id, status in [
        ("velha", "completed"),
        ("rodando", "running"),
        ("falhou", "failed"),
        ("rodando-2", "running"),
    ]:
        run_store.create_run(
            run_id=run_id,
            workflow_id="demo",
            workspace=tmp_path,
            user_prompt=run_id,
            steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
        )
        run_store.update_run(run_id, status=status)

    items = HistoryCatalog(tmp_path).list_items()
    assert {item.run_id for item in items[:2]} == {"rodando", "rodando-2"}, (
        "as runs em execução têm que vir primeiro"
    )
    assert all(item.status is HistoryStatus.IN_PROGRESS for item in items[:2])
    assert all(item.status is not HistoryStatus.IN_PROGRESS for item in items[2:])

    # Dentro de cada grupo a ordem do banco é preservada (mais recente no topo):
    # a reordenação é estável, não um `sort` que embaralha o resto.
    from_db = [record.id for record in run_store.list_runs(tmp_path)]
    for group in (items[:2], items[2:]):
        ids = [item.run_id for item in group]
        assert ids == [run_id for run_id in from_db if run_id in set(ids)]


def test_searching_keeps_the_running_run_on_top(tmp_path: Path):
    from pulse.history.catalog import HistoryCatalog

    for run_id, status in [("alfa-velha", "completed"), ("alfa-viva", "running")]:
        run_store.create_run(
            run_id=run_id,
            workflow_id="demo",
            workspace=tmp_path,
            user_prompt="alfa",
            steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
        )
        run_store.update_run(run_id, status=status)

    found = HistoryCatalog(tmp_path).search("alfa")
    assert [item.run_id for item in found] == ["alfa-viva", "alfa-velha"]
