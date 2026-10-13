"""The cockpit shows how many tokens each step holds in context, live, and the run's sum.

The figure comes only from the agent's `usage_update`; the daemon relays it raw
inside `session.update`, so attaching to a run replays it like any other update.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pulse.client.protocol import REPLAY_END
from pulse.client.run_session import EngineRunSession
from pulse.history.events import ContextUsage
from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState
from tests.conftest import configure_from_db, make_workflow

TWO = [("one", "Um"), ("two", "Dois")]


def _usage(used: Any, size: Any = 200_000) -> dict[str, Any]:
    return {"update": {"sessionUpdate": "usage_update", "used": used, "size": size}}


def _cockpit() -> tuple[CockpitState, CockpitSink]:
    state = CockpitState()
    make_workflow("demo", steps=TWO)
    configure_from_db(state, "demo")
    return state, CockpitSink(state)


def test_a_usage_update_lands_on_the_running_step():
    state, sink = _cockpit()
    sink.begin_phase("Dois")

    sink.handle_update(_usage(42_000))

    assert state.phases[1].context == ContextUsage(used=42_000)
    assert state.phases[0].context is None


def test_the_latest_reading_replaces_the_previous_one():
    """Context occupancy is a level, not a sum: compaction can lower it."""
    state, sink = _cockpit()
    sink.begin_phase("Um")

    sink.handle_update(_usage(80_000))
    sink.handle_update(_usage(30_000))

    assert state.phases[0].context == ContextUsage(used=30_000)


def test_a_reading_with_no_running_step_is_dropped():
    state, sink = _cockpit()

    sink.handle_update(_usage(42_000))

    assert [phase.context for phase in state.phases] == [None, None]


def test_a_malformed_reading_keeps_the_last_good_one():
    state, sink = _cockpit()
    sink.begin_phase("Um")
    sink.handle_update(_usage(42_000))

    sink.handle_update(_usage("lots"))

    assert state.phases[0].context == ContextUsage(used=42_000)


def test_the_run_total_sums_the_last_reading_of_every_step():
    state, sink = _cockpit()
    sink.begin_phase("Um")
    sink.handle_update(_usage(30_000))
    sink.begin_phase("Dois")
    sink.handle_update(_usage(12_000))

    assert state.context_total() == 42_000
    assert state.run_context_label() == "42k tokens"


def test_a_run_without_readings_shows_no_context():
    state, _ = _cockpit()

    assert state.context_total() == 0
    assert state.run_context_label() == ""
    assert [state.context_label(phase) for phase in state.phases] == ["", ""]


def test_each_step_shows_its_own_tokens():
    state, sink = _cockpit()
    sink.begin_phase("Um")
    sink.handle_update(_usage(42_000))
    sink.begin_phase("Dois")
    sink.handle_update(_usage(1_500))

    assert [state.context_label(phase) for phase in state.phases] == [
        "42k tokens",
        "1k tokens",
    ]


class _ReplayClient:
    def stream_events(self, run_id: str, *, after: int = 0):
        yield {"type": "phase.begin", "title": "Um"}
        yield {"type": "session.update", "params": _usage(64_000)}
        yield {"type": REPLAY_END, "count": 2}
        yield {"type": "run.finished", "exit_code": 0}


class _NoPrompts:
    def handle(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("no prompt expected")


def test_attaching_to_a_run_rebuilds_the_context_from_the_replay():
    state, sink = _cockpit()
    session = EngineRunSession(stream=sink, prompt_handler=_NoPrompts(), client=_ReplayClient())

    session.attach("run-live")

    assert state.phases[0].context == ContextUsage(used=64_000)


def test_the_sidebar_and_header_show_the_tokens():
    """The step's tokens sit beside its running clock; the header carries the run's sum."""

    async def run() -> None:
        from textual.app import App, ComposeResult

        from pulse.tui.widgets.app_header import AppHeader
        from pulse.tui.widgets.phase_sidebar import PhaseSidebar

        state, sink = _cockpit()
        sink.begin_phase("Um")
        sink.handle_update(_usage(42_000))
        sidebar = PhaseSidebar(state, id="phase-sidebar")

        class Harness(App[None]):
            def compose(self) -> ComposeResult:
                yield AppHeader()
                yield sidebar

            def on_mount(self) -> None:
                self.query_one(AppHeader).sync_from_state(state)
                sidebar.sync_from_state(state)

        app = Harness()
        async with app.run_test(size=(140, 32)) as pilot:
            await pilot.pause()
            assert app.query_one(AppHeader).run_label.endswith("· 42k tokens")
            running = sidebar._render_item(state, state.phases[0], selected=True, now=0.0)
            meta_line = running.plain.splitlines()[1]
            assert meta_line.endswith(" · 42k tokens")
            assert (
                "tokens"
                not in sidebar._render_item(state, state.phases[1], selected=False, now=0.0).plain
            )

    asyncio.run(run())
