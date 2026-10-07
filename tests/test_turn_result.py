"""The runner's turn result is parsed once, at the engine boundary.

The engine used to read the runner's `dict` with string keys at every branch; a
renamed key silently turned a cancel into a delivery. `TurnResult` is the one
place that knows those keys.
"""

from __future__ import annotations

import pytest

from pulse.orchestrator.turn import TurnResult


@pytest.mark.parametrize(
    "raw",
    [
        {"outcome": "cancel"},
        {"outcome": "cancelled"},
        {"stopReason": "cancelled"},
        {"stopReason": "cancelled", "approved": True, "phaseSummary": "done"},
    ],
)
def test_any_cancel_marker_is_a_cancelled_turn(raw: dict) -> None:
    """A cancel must never be read as a delivery, whatever else the dict says."""
    assert TurnResult.parse(raw).cancelled is True


def test_a_finished_turn_is_not_cancelled() -> None:
    turn = TurnResult.parse({"stopReason": "end_turn", "phaseSummary": "ok"})

    assert turn.cancelled is False
    assert turn.ended_cleanly is True
    assert turn.summary == "ok"


def test_the_skip_outcome_is_a_skipped_turn() -> None:
    assert TurnResult.parse({"approved": False, "outcome": "skip"}).skipped is True
    assert TurnResult.parse({"approved": True, "outcome": "approve"}).skipped is False


@pytest.mark.parametrize("stop_reason", ["end_turn", "end", "stop"])
def test_known_stop_reasons_end_the_turn_cleanly(stop_reason: str) -> None:
    assert TurnResult.parse({"stopReason": stop_reason}).ended_cleanly is True


@pytest.mark.parametrize("raw", [{}, {"stopReason": "max_tokens"}, {"stopReason": None}])
def test_other_stop_reasons_do_not_end_the_turn_cleanly(raw: dict) -> None:
    """Fail safe: an unknown or missing stop reason is not a success."""
    assert TurnResult.parse(raw).ended_cleanly is False


def test_approval_is_true_only_when_the_runner_says_so() -> None:
    assert TurnResult.parse({"approved": True}).approved is True
    assert TurnResult.parse({"approved": False}).approved is False
    assert TurnResult.parse({}).approved is False


def test_blank_approval_answers_mean_the_agent_never_asked() -> None:
    assert TurnResult.parse({"approvalAnswers": "  \n"}).has_approval_answers is False
    assert TurnResult.parse({"approvalAnswers": "Q1: sim"}).has_approval_answers is True


def test_stop_reason_is_kept_for_the_failure_message() -> None:
    assert TurnResult.parse({"stopReason": "max_tokens"}).stop_reason == "max_tokens"
    assert TurnResult.parse({}).stop_reason == ""
