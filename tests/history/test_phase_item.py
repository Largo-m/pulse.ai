"""`PhaseItem` owns its clock: callers state the transition, not the fields."""

from __future__ import annotations

import pytest

from pulse.domain.run import StepStatus
from pulse.history.events import PhaseItem, PhaseStatus


def _running(started_at: float = 10.0) -> PhaseItem:
    return PhaseItem(id="build", label="Build", status=PhaseStatus.RUNNING, started_at=started_at)


def test_the_screen_shares_the_persisted_step_vocabulary():
    """A stored `StepStatus` is shown as-is; a second enum would need a translation table."""
    assert PhaseStatus is StepStatus


@pytest.mark.parametrize("status", [PhaseStatus.BLOCKED, PhaseStatus.FAILED, PhaseStatus.SKIPPED])
def test_ending_a_running_step_stops_its_clock_at_that_moment(status):
    phase = _running(started_at=10.0)

    phase.end_as(status, now=25.0)

    assert (phase.status, phase.ended_at) == (status, 25.0)
    assert phase.elapsed_label(now=999.0) == "00:15"


def test_ending_a_step_that_never_ran_keeps_it_without_a_duration():
    phase = PhaseItem(id="review", label="Review")

    phase.end_as(PhaseStatus.SKIPPED, now=25.0)

    assert (phase.status, phase.started_at, phase.ended_at) == (PhaseStatus.SKIPPED, None, None)
    assert phase.elapsed_label() == ""


def test_ending_a_finished_step_keeps_its_original_end():
    phase = PhaseItem(
        id="build", label="Build", status=PhaseStatus.DONE, started_at=10.0, ended_at=12.0
    )

    phase.end_as(PhaseStatus.BLOCKED, now=25.0)

    assert (phase.status, phase.ended_at) == (PhaseStatus.BLOCKED, 12.0)


def test_a_restarted_step_is_pending_with_no_time_spent():
    phase = _running()
    phase.begin_waiting(now=12.0)
    phase.end_waiting(now=14.0)
    phase.begin_waiting(now=15.0)

    phase.restart()

    assert phase == PhaseItem(id="build", label="Build")
    assert phase.display_status() == "pending"


def test_a_stored_duration_is_shown_without_ticking():
    phase = PhaseItem(id="build", label="Build", status=PhaseStatus.RUNNING, waiting_total=3.0)

    phase.show_closed(75.0)

    assert phase.elapsed_label(now=10_000.0) == "01:15"
    assert phase.closed_seconds() == 75.0


def test_a_resumed_clock_ticks_from_its_start_net_of_past_waits():
    phase = PhaseItem(id="build", label="Build", status=PhaseStatus.RUNNING, ended_at=5.0)

    phase.resume_clock(started_at=100.0, waiting_total=20.0)

    assert phase.ended_at is None
    assert phase.elapsed_label(now=190.0) == "01:10"


def test_a_resumed_clock_ignores_a_negative_stored_wait():
    phase = PhaseItem(id="build", label="Build", status=PhaseStatus.RUNNING)

    phase.resume_clock(started_at=100.0, waiting_total=-5.0)

    assert phase.waiting_total == 0.0
