"""O prazo de `session/prompt`: silêncio do agente, não duração do trabalho.

Um step que implementa uma task leva o tempo que levar, e uma aprovação leva o
tempo que o usuário levar. Contar o total derrubava os dois por "timeout".
"""

from __future__ import annotations

import threading
import time

from pulse.acp.session_runner import AcpSessionRunner


def _runner(timeout: float) -> AcpSessionRunner:
    """Runner sem processo: só o suficiente para exercitar `_request`."""
    runner = AcpSessionRunner(["fake-agent"], cwd="/repo", timeout_seconds=timeout)
    runner._send = lambda _payload: None  # type: ignore[method-assign]
    runner._session_id = "sess-1"
    return runner


def _reply_after(runner: AcpSessionRunner, delay: float, result: dict) -> threading.Thread:
    def later() -> None:
        time.sleep(delay)
        runner._responses[1] = {"id": 1, "result": result}
        runner._response_queue.put(1)

    thread = threading.Thread(target=later, daemon=True)
    thread.start()
    return thread


def test_an_agent_that_keeps_talking_does_not_time_out():
    """Cada linha recebida renova o prazo: trabalhar não é travar."""
    runner = _runner(0.3)

    def chatter() -> None:
        for _ in range(6):
            time.sleep(0.1)
            runner._activity = time.monotonic()
        runner._responses[1] = {"id": 1, "result": {"stopReason": "end_turn"}}
        runner._response_queue.put(1)

    threading.Thread(target=chatter, daemon=True).start()

    # 0,6s de trabalho com prazo de 0,3s — e mesmo assim fecha o turno.
    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}


def test_a_question_on_screen_does_not_spend_the_agents_clock():
    """Esperar o usuário é espera nossa; não pode virar culpa do agente."""
    runner = _runner(0.3)

    def asking() -> None:
        runner._begin_user_wait()
        time.sleep(0.7)
        runner._end_user_wait()
        runner._responses[1] = {"id": 1, "result": {"stopReason": "end_turn"}}
        runner._response_queue.put(1)

    threading.Thread(target=asking, daemon=True).start()

    assert runner._request("session/prompt", {}) == {"stopReason": "end_turn"}


def test_silence_beyond_the_deadline_still_times_out():
    runner = _runner(0.2)

    try:
        runner._request("session/prompt", {})
    except TimeoutError as error:
        assert "session/prompt" in str(error)
    else:  # pragma: no cover - o teste falha antes
        raise AssertionError("silêncio longo demais tem de estourar o prazo")


def test_a_short_request_keeps_the_total_deadline():
    """`initialize` e afins não ganham relógio de silêncio: são imediatos."""
    runner = _runner(0.3)
    _reply_after(runner, 0.5, {"protocolVersion": 1})

    try:
        runner._request("initialize", {})
    except TimeoutError:
        pass
    else:  # pragma: no cover - o teste falha antes
        raise AssertionError("o prazo total de um request curto não é renovado")


def test_a_dead_process_ends_the_wait_right_away():
    """Sem processo não há resposta para esperar — nem 10 minutos de prazo."""

    class _Dead:
        def poll(self) -> int:
            return 1

    runner = _runner(600.0)
    runner._process = _Dead()  # type: ignore[assignment]

    started = time.monotonic()
    try:
        runner._request("session/close", {"sessionId": "sess-1"})
    except RuntimeError as error:
        assert "encerrou" in str(error)
    else:  # pragma: no cover - o teste falha antes
        raise AssertionError("processo morto tem de interromper a espera")
    assert time.monotonic() - started < 5.0
