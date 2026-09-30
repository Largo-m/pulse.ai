from __future__ import annotations

from pulse.runcontrol import RUN_STOPPED, STOPPED, RunControl


def test_stop_is_a_single_transition():
    seen: list[str] = []
    control = RunControl(on_change=seen.append)

    assert control.stop() is True
    assert control.stop() is False, "parar de novo não é uma transição"
    assert control.stopped is True
    assert control.interrupted is True

    assert seen == [STOPPED]


def test_checkpoint_blocks_only_after_stop():
    control = RunControl()
    assert control.checkpoint() is True
    assert control.interrupted is False

    control.stop()

    assert control.checkpoint() is False, "run parada não segue para o próximo step"


def test_stopped_exit_code_is_not_a_failure_code():
    assert RUN_STOPPED not in {0, 1, 2}


def test_on_change_failure_never_breaks_the_caller():
    def _explode(_kind: str) -> None:
        raise RuntimeError("bus caiu")

    control = RunControl(on_change=_explode)
    assert control.stop() is True
    assert control.stopped is True
