from __future__ import annotations

import threading
import time

from pulse.runcontrol import PAUSED, RESUMED, RUN_STOPPED, STOPPED, RunControl


def test_pause_resume_cycle_notifies_once_per_transition():
    seen: list[str] = []
    control = RunControl(on_change=seen.append)

    assert control.pause() is True
    assert control.pause() is False, "pausar de novo não é uma transição"
    assert control.paused is True
    assert control.interrupted is True

    assert control.resume() is True
    assert control.resume() is False
    assert control.paused is False
    assert control.interrupted is False

    assert seen == [PAUSED, RESUMED]


def test_wait_while_paused_holds_until_resume():
    control = RunControl()
    control.pause()
    released: list[bool] = []

    def _worker() -> None:
        released.append(control.wait_while_paused())

    thread = threading.Thread(target=_worker)
    thread.start()
    time.sleep(0.1)
    assert released == [], "a barreira tem de segurar enquanto pausado"

    control.resume()
    thread.join(timeout=2)
    assert released == [True], "ao retomar, o fluxo segue"


def test_stop_releases_the_barrier_and_refuses_to_resume():
    seen: list[str] = []
    control = RunControl(on_change=seen.append)
    control.pause()
    released: list[bool] = []

    thread = threading.Thread(target=lambda: released.append(control.wait_while_paused()))
    thread.start()
    time.sleep(0.05)

    control.stop()
    thread.join(timeout=2)

    assert released == [False], "parada solta a barreira mandando encerrar"
    assert control.stopped is True
    assert control.interrupted is True
    assert control.resume() is False, "run parada não volta a rodar"
    assert seen == [PAUSED, STOPPED]


def test_checkpoint_is_transparent_when_nothing_was_requested():
    control = RunControl()
    assert control.checkpoint() is True
    assert control.interrupted is False


def test_stopped_exit_code_is_not_a_failure_code():
    assert RUN_STOPPED not in {0, 1, 2}


def test_on_change_failure_never_breaks_the_caller():
    def _explode(_kind: str) -> None:
        raise RuntimeError("bus caiu")

    control = RunControl(on_change=_explode)
    assert control.pause() is True
    assert control.paused is True
