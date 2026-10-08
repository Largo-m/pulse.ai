"""The daemon's adapters implement the ports the engine calls, with no optional method.

The engine used to probe the stream with `getattr`; a sink missing a method now
breaks here instead of silently dropping that part of the screen.
"""

from __future__ import annotations

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
