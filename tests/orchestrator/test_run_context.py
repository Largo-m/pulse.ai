"""`run.context`: where the run works and on which branch, from engine to screen.

It is a regular bus event on purpose: replay delivers it to late attachers, and
the screen reopens pointing at the right worktree without a new route.
"""

from __future__ import annotations

from pathlib import Path

from pulse.client.protocol import REPLAY_END
from pulse.client.run_session import EngineRunSession
from pulse.daemon.adapters import ApiStreamSink
from pulse.daemon.events import EventBus
from pulse.domain.ports import NullPromptPort
from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.state import CockpitState
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import EngineHarness, approved_turn


class _ReplayClient:
    """Delivers a fixed list of events, like a run replay."""

    def __init__(self, events: list[dict]) -> None:
        self._events = events

    def stream_events(self, run_id: str, *, after: int = 0):
        yield from self._events

    def close(self) -> None:
        return None

    def answer_prompt(self, prompt_id: str, answer):
        return {"ok": True}


def _replayed(bus: EventBus) -> list[dict]:
    """The past the bus redelivers to whoever attaches now."""
    events: list[dict] = []
    for event in bus.subscribe(after=0):
        if event.get("type") == REPLAY_END:
            break
        events.append(event)
    return events


def test_daemon_sink_publishes_the_context():
    bus = EventBus()
    ApiStreamSink(bus).set_context(cwd="/repo/wt", branch="pulse/demo-abc")
    assert {"type": "run.context", "cwd": "/repo/wt", "branch": "pulse/demo-abc"} in _replayed(bus)


def test_engine_announces_the_context_before_any_step(tmp_path: Path):
    """The artifacts panel depends on this to know where to look for files."""
    make_workflow("demo", steps=[("one", "Um")])
    runner = FakeAgentSession([approved_turn()])
    calls: list[str] = []
    runner.stream.set_context = lambda *, cwd, branch: calls.append(f"context:{cwd}")
    runner.stream.begin_phase = lambda title: calls.append(f"phase:{title}")
    runner.run_isolated_phase = _beginning_a_phase(runner)

    EngineHarness(tmp_path).run(
        runner,
        workflow_id="demo",
        user_prompt="x",
    )

    assert calls == [f"context:{tmp_path}", "phase:Um"]


def _beginning_a_phase(runner: FakeAgentSession):
    """The real runner opens a phase on the stream before the agent's first turn."""
    original = runner.run_isolated_phase

    def run(*, phase_label: str, **kwargs):
        runner.stream.begin_phase(phase_label)
        return original(phase_label=phase_label, **kwargs)

    return run


def test_client_forwards_the_context_to_the_sink():
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/projeto")
    session = EngineRunSession(
        stream=sink,
        prompt_handler=NullPromptPort(),
        client=_ReplayClient(
            [
                {"type": "run.context", "cwd": "/projeto/.wt", "branch": "pulse/demo-abc"},
                {"type": "run.finished", "exit_code": 0},
            ]
        ),
    )
    session.attach("run-1")

    assert state.branch_label == "pulse/demo-abc"
    assert sink._cwd == "/projeto/.wt"


def test_context_tells_the_screen_to_repoint_the_panel():
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    seen: list[str] = []
    sink = CockpitSink(state, cwd="/projeto", on_context=seen.append)

    sink.set_context(cwd="/projeto/.wt", branch="pulse/demo-abc")

    assert seen == ["/projeto/.wt"]


def test_context_without_worktree_only_sets_the_branch():
    """Run at the project root: the branch shows up, the cwd does not change."""
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    sink = CockpitSink(state, cwd="/projeto")

    sink.set_context(cwd="/projeto", branch="main")

    assert state.branch_label == "main"
    assert sink._cwd == "/projeto"
