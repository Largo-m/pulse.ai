"""`run.context`: onde a run trabalha e em que branch, do motor até a tela.

É um evento como qualquer outro do barramento — e é de propósito: assim o
replay o entrega a quem anexa depois, e a tela reabre apontando para o
worktree certo sem rota nova.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tests.conftest import make_workflow

from pulse.client.run_session import EngineRunSession
from pulse.daemon.adapters import ApiStreamSink
from pulse.daemon.events import EventBus
from pulse.daemon.protocol import REPLAY_END
from pulse.orchestrator.engine import _announce_context
from pulse.ports import NullStreamSink
from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState


class _ReplayClient:
    """Entrega uma lista fixa de eventos, como o replay de uma run."""

    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def stream_events(self, run_id: str, *, after: int = 0):
        yield from self._events

    def close(self) -> None:
        return None

    def answer_prompt(self, prompt_id: str, answer):
        return {"ok": True}


def _replayed(bus: EventBus) -> list[dict]:
    """O passado que o barramento reentrega a quem anexa agora."""
    events: list[dict] = []
    for event in bus.subscribe(after=0):
        if event.get("type") == REPLAY_END:
            break
        events.append(event)
    return events


def test_sink_do_daemon_publica_o_contexto():
    bus = EventBus()
    ApiStreamSink(bus).set_context(cwd="/tmp/wt", branch="pulse/demo-abc")
    assert {"type": "run.context", "cwd": "/tmp/wt", "branch": "pulse/demo-abc"} in _replayed(bus)


def test_motor_anuncia_antes_de_qualquer_step(tmp_path: Path):
    """O painel de artefatos depende disto para saber onde procurar arquivo."""
    stream = MagicMock()
    _announce_context(stream, tmp_path / "wt", "pulse/demo-abc")
    stream.set_context.assert_called_once_with(cwd=str(tmp_path / "wt"), branch="pulse/demo-abc")


def test_stream_sem_set_context_nao_quebra():
    """CLI e testes passam sinks que não sabem de branch nenhuma."""
    _announce_context(NullStreamSink(), Path("/tmp"), "main")
    _announce_context(None, Path("/tmp"), "main")


def test_cliente_repassa_o_contexto_ao_sink():
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/projeto")
    session = EngineRunSession(
        stream=sink,
        prompt_handler=MagicMock(),
        client=_ReplayClient(
            [
                {"type": "run.context", "cwd": "/projeto/.wt", "branch": "pulse/demo-abc"},
                {"type": "run.finished", "exit_code": 0},
            ]
        ),
    )
    session.attach("run-1")

    assert state.branch_label == "pulse/demo-abc"
    # O sink passou a procurar artefato onde o agente escreveu.
    assert sink._cwd == "/projeto/.wt"


def test_contexto_avisa_a_tela_para_reapontar_o_painel():
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    seen: list[str] = []
    sink = CockpitSink(state, cwd="/projeto", on_context=seen.append)

    sink.set_context(cwd="/projeto/.wt", branch="pulse/demo-abc")

    assert seen == ["/projeto/.wt"]


def test_contexto_sem_worktree_so_marca_a_branch():
    """Run na raiz do projeto: a branch aparece, o cwd não muda."""
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/projeto")

    sink.set_context(cwd="/projeto", branch="main")

    assert state.branch_label == "main"
    assert sink._cwd == "/projeto"
