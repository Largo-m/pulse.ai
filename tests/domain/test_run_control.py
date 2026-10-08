from __future__ import annotations

import pytest

from pulse.domain.control import RUN_STOPPED, STOPPED, RunControl


def test_stop_is_a_single_transition():
    seen: list[str] = []
    control = RunControl(on_change=seen.append)

    assert control.stop() is True
    assert control.stop() is False, "stopping again is not a transition"
    assert control.interrupted is True

    assert seen == [STOPPED]


def test_checkpoint_blocks_only_after_stop():
    control = RunControl()
    assert control.checkpoint() is True
    assert control.interrupted is False

    control.stop()

    assert control.checkpoint() is False, "a stopped run does not move on to the next step"


def test_stopped_exit_code_is_not_a_failure_code():
    assert RUN_STOPPED not in {0, 1, 2}


def test_a_failing_listener_still_leaves_the_run_stopped():
    """The failure surfaces to whoever stopped, but the stop already happened."""

    def _explode(_kind: str) -> None:
        raise RuntimeError("bus down")

    control = RunControl(on_change=_explode)
    with pytest.raises(RuntimeError, match="bus down"):
        control.stop()

    assert control.interrupted is True
    assert control.checkpoint() is False
