"""The daemon's adapters implement the ports the engine calls, with no optional method.

The engine used to probe the stream with `getattr`; a sink missing a method now
breaks here instead of silently dropping that part of the screen.
"""

from __future__ import annotations

import pytest

from pulse.client.protocol import REPLAY_END
from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.domain.ports import PromptPort, StreamSink


def _replayed(bus: EventBus) -> list[dict]:
    events: list[dict] = []
    for event in bus.subscribe(after=0):
        if event.get("type") == REPLAY_END:
            break
        events.append(event)
    return events


def test_the_api_sink_and_prompt_port_implement_the_ports():
    bus = EventBus()

    assert isinstance(ApiStreamSink(bus), StreamSink)
    assert isinstance(ApiPromptPort(PromptCorrelator(bus)), PromptPort)


def test_phase_statuses_go_out_as_one_sync_event_with_every_list():
    """The client rebuilds the sidebar from this event alone, so no list may be missing."""
    bus = EventBus()

    ApiStreamSink(bus).apply_phase_statuses(
        steps=[{"id": "one", "label": "Um", "rounds": 2}],
        done_ids=("one",),
    )

    assert _replayed(bus) == [
        {
            "type": "phases.sync",
            "steps": [{"id": "one", "label": "Um", "rounds": 2}],
            "done_ids": ["one"],
            "skipped_ids": [],
            "failed_ids": [],
            "blocked_ids": [],
        }
    ]


class _AnsweringCorrelator:
    """Stands in for the client: answers every prompt with the same value."""

    def __init__(self, answer: object) -> None:
        self._answer = answer
        self.asked: list[tuple[str, dict]] = []

    def request(self, kind: str, payload: dict, *, timeout: float | None = None) -> object:
        self.asked.append((kind, payload))
        return self._answer


@pytest.mark.parametrize(("answer", "picked"), [({"index": 1}, "retry"), (0, "skip")])
def test_a_choice_answer_maps_back_to_the_engine_value(answer: object, picked: str):
    """The client only sends a position; the engine gets back its own value, not the label."""
    port = ApiPromptPort(_AnsweringCorrelator(answer))

    assert port.select_choice("?", [("Skip", "skip"), ("Retry", "retry")]) == picked


@pytest.mark.parametrize("answer", [None, {"index": 7}, {"index": "1"}, {"index": True}, "retry"])
def test_a_choice_answer_that_names_no_choice_is_no_choice(answer: object):
    """An answer outside the offered list must not reach the engine as if it were a value."""
    port = ApiPromptPort(_AnsweringCorrelator(answer))

    assert port.select_choice("?", [("Skip", "skip"), ("Retry", "retry")]) is None


@pytest.mark.parametrize("answer", [None, "yes", ["B"]])
def test_an_ask_question_answer_that_is_not_an_object_cancels(answer: object):
    """ACP expects an outcome object; anything else would break the agent's JSON-RPC reply."""
    port = ApiPromptPort(_AnsweringCorrelator(answer))

    assert port.respond_to_ask_question({"questions": []}) == {"outcome": {"outcome": "cancelled"}}


def test_an_unknown_policy_reaches_a_person_instead_of_being_applied():
    """A policy typo in the request asks, as `parse_policy` does for the config."""
    correlator = _AnsweringCorrelator({"outcome": {"outcome": "selected", "optionId": "no"}})
    params = {"toolCall": {"kind": "edit"}, "options": [{"optionId": "ok", "kind": "allow_once"}]}

    answer = ApiPromptPort(correlator).respond_to_permission(params, policy="AUTO_APPROVE")

    assert answer == {"outcome": {"outcome": "selected", "optionId": "no"}}
    assert [kind for kind, _ in correlator.asked] == ["permission"]
