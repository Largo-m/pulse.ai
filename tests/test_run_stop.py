from __future__ import annotations

from pulse.acp import session_runner as session_runner_module
from pulse.acp.session_runner import AcpSessionRunner
from pulse.runcontrol import RunControl


def _runner(control: RunControl) -> tuple[AcpSessionRunner, list[dict]]:
    """Runner sem processo: só o suficiente para exercitar `_request`."""
    runner = AcpSessionRunner(["fake-agent"], cwd="/repo", control=control)
    sent: list[dict] = []
    runner._send = sent.append  # type: ignore[method-assign]
    runner._session_id = "sess-1"
    return runner, sent


def _reply(runner: AcpSessionRunner, request_id: int, result: dict) -> None:
    runner._responses[request_id] = {"id": request_id, "result": result}
    runner._response_queue.put(request_id)


def test_stop_cancels_the_turn_in_flight(monkeypatch):
    """Parar manda `session/cancel` e devolve o turno como cancelado."""
    monkeypatch.setattr(session_runner_module, "CANCEL_GRACE_SECONDS", 0.3)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "cancelled"}
    methods = [payload.get("method") for payload in sent]
    assert methods == ["session/prompt", "session/cancel"]
    assert sent[1]["params"] == {"sessionId": "sess-1"}
    assert "id" not in sent[1], "cancel é notificação, não request"


def test_cancel_is_sent_once_even_esperando_o_agente(monkeypatch):
    monkeypatch.setattr(session_runner_module, "CANCEL_GRACE_SECONDS", 0.5)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)

    runner._request("session/prompt", {"sessionId": "sess-1"})

    assert [payload.get("method") for payload in sent].count("session/cancel") == 1


def test_agent_answer_to_the_cancelled_turn_wins(monkeypatch):
    """Se o agente fecha o turno sozinho, é a resposta dele que vale."""
    monkeypatch.setattr(session_runner_module, "CANCEL_GRACE_SECONDS", 5.0)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)
    _reply(runner, 1, {"stopReason": "cancelled", "phaseSummary": "parcial"})

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "cancelled", "phaseSummary": "parcial"}


def test_sem_parada_o_turno_segue_normal():
    runner, sent = _runner(RunControl())
    _reply(runner, 1, {"stopReason": "end_turn"})

    result = runner._request("session/prompt", {"sessionId": "sess-1"})

    assert result == {"stopReason": "end_turn"}
    assert [payload.get("method") for payload in sent] == ["session/prompt"]


def test_parada_nao_corta_requests_curtos_do_protocolo(monkeypatch):
    """`initialize`, `session/new` e afins não são cancelados no meio."""
    monkeypatch.setattr(session_runner_module, "CANCEL_GRACE_SECONDS", 0.2)
    control = RunControl()
    control.stop()
    runner, sent = _runner(control)
    _reply(runner, 1, {"sessionId": "sess-2"})

    result = runner._request("session/new", {"cwd": "/repo"})

    assert result == {"sessionId": "sess-2"}
    assert [payload.get("method") for payload in sent] == ["session/new"]
