from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from pulse.tui.app import PulseApp
from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.screens.home import HomeScreen
from pulse.tui.state import LogKind, PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSidebar
from tests.conftest import make_workflow


def test_pulse_app_has_cockpit_theme():
    app = PulseApp()
    assert app.CSS == COCKPIT_CSS
    assert "#A2D729" in COCKPIT_CSS
    assert "SettingsScreen" in COCKPIT_CSS
    assert "OnboardingScreen" in COCKPIT_CSS
    assert "HistoryListScreen" in COCKPIT_CSS


def test_cockpit_screen_initial_state():
    make_workflow("demo", steps=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")])
    screen = CockpitScreen("demo", "demo feature")
    assert len(screen.state.phases) == 4
    assert all(phase.status == PhaseStatus.PENDING for phase in screen.state.phases)
    assert screen.workflow_id == "demo"
    assert screen.state.entries == []


def test_home_opens_settings_screen(monkeypatch):
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            def compose(self) -> ComposeResult:
                yield Static("ok")

            def open_settings(self) -> None:
                called.append("settings")

        called: list[str] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.app.open_settings()
            assert called == ["settings"]

    asyncio.run(run())


def test_log_stream_and_sidebar_render_text():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        state_holder: dict = {}

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                make_workflow("quick", steps=[("plan", "Planejar"), ("run", "Implementar")])
                screen = CockpitScreen("quick", "demo")
                state_holder["screen"] = screen
                with Horizontal(id="cockpit-body"):
                    yield PhaseSidebar(screen.state, id="phase-sidebar")
                    yield LogStream(screen.state, id="log-stream")

            def on_mount(self) -> None:
                screen = state_holder["screen"]
                screen.sink.begin_phase("Planejar")
                screen.sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": "t1",
                            "title": "Read File",
                            "kind": "read",
                            "rawInput": {"path": "/repo/pulse/cli.py"},
                        }
                    }
                )
                screen.sink.handle_update(
                    {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": "Plano pronto"},
                        }
                    }
                )
                screen.sink.error(
                    "Classificação cancelada",
                    "O agente não definiu o flow (quick ou full).",
                )
                self.query_one(PhaseSidebar).sync_from_state(screen.state)
                self.query_one(LogStream).sync_from_state(screen.state, force=True)

        app = Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            content = str(app.query_one("#stream-content").render())
            phases = str(app.query_one("#phase-content").render())
            assert "Read" in content
            assert "Plano" in content
            assert "Assistente" in content
            assert "Erro" in content
            assert "Classificação cancelada" in content
            assert "flow" in content
            assert "Planejar" in phases
            assert LogKind.READ in {entry.kind for entry in state_holder["screen"].state.entries}

    asyncio.run(run())


def test_cockpit_layout_keeps_header_and_body_sizes():
    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal

        from pulse.tui.state import CockpitState
        from pulse.tui.widgets.app_footer import AppFooter
        from pulse.tui.widgets.app_header import AppHeader

        make_workflow("demo", steps=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")])
        state = CockpitState()
        state.configure_workflow("demo")

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield AppHeader()
                with Horizontal(id="cockpit-body"):
                    yield PhaseSidebar(state, id="phase-sidebar")
                    yield LogStream(state, id="log-stream")
                yield AppFooter()

            def on_mount(self) -> None:
                self.query_one(AppHeader).sync_from_state(state)
                self.query_one(PhaseSidebar).sync_from_state(state)
                self.query_one(LogStream).sync_from_state(state, force=True)
                self.query_one(AppFooter).sync_from_state(state)

        app = Harness()
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause()
            header = app.query_one(AppHeader)
            body = app.query_one("#cockpit-body")
            footer = app.query_one(AppFooter)
            sidebar = app.query_one(PhaseSidebar)
            stream = app.query_one(LogStream)
            assert header.size.height == 3
            assert footer.size.height == 1
            assert body.size.height == 28
            assert body.size.width == 120
            assert sidebar.size.height >= 24
            assert stream.size.height >= 24
            assert sidebar.size.width >= 20
            assert stream.size.width > sidebar.size.width
            assert "0/4" in str(app.query_one("#run-status").render())

    asyncio.run(run())


def _home_option_ids(screen) -> list[str]:
    from textual.widgets import OptionList

    options = screen.query_one("#home-options", OptionList)
    return [str(options.get_option_at_index(index).id) for index in range(options.option_count)]


def _highlighted(option_id: str):
    return _selected(option_id)


def _selected(option_id: str):
    """`on_option_selected` only reads `option_id`; building the real event needs the widget."""
    from types import SimpleNamespace

    return SimpleNamespace(option_id=option_id)


def test_home_hides_the_loops_behind_new_session(monkeypatch):
    """The root menu does not grow with the database: loops live one level below."""
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

            def open_cockpit(self, workflow_id: str, prompt: str) -> None:
                opened.append((workflow_id, prompt))

        opened: list[tuple[str, str]] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()

            root = _home_option_ids(screen)
            assert root == ["session", "history", "settings", "exit"]

            screen.on_option_selected(_selected("session"))
            await pilot.pause()
            loops = _home_option_ids(screen)
            assert "workflow:new-issue" in loops
            assert "workflow:quick-fix" in loops
            assert loops[-1] == "back"
            assert "workflow:default" not in loops

            screen.action_back()
            await pilot.pause()
            assert _home_option_ids(screen) == root

    asyncio.run(run())


def test_home_starts_the_chosen_loop_with_the_typed_prompt(monkeypatch):
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input, Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

            def open_cockpit(self, workflow_id: str, prompt: str) -> None:
                opened.append((workflow_id, prompt))

        opened: list[tuple[str, str]] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.on_option_selected(_selected("session"))
            await pilot.pause()
            screen.on_option_selected(_selected("workflow:new-issue"))
            await pilot.pause()

            prompt_input = screen.query_one("#workflow-prompt", Input)
            assert prompt_input.display is True

            prompt_input.value = "exportar relatório em csv"
            screen.on_prompt_submitted(Input.Submitted(prompt_input, prompt_input.value))
            await pilot.pause()

            assert opened == [("new-issue", "exportar relatório em csv")]

    asyncio.run(run())


def test_escape_closes_the_prompt_before_leaving_the_submenu(monkeypatch):
    """Esc goes one step at a time: closes the input, then returns to the root."""
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input, Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.on_option_selected(_selected("session"))
            screen.on_option_selected(_selected("workflow:new-issue"))
            await pilot.pause()

            screen.action_back()
            await pilot.pause()
            assert screen.query_one("#workflow-prompt", Input).display is False
            assert "workflow:new-issue" in _home_option_ids(screen)

            screen.action_back()
            await pilot.pause()
            assert _home_option_ids(screen) == ["session", "history", "settings", "exit"]

    asyncio.run(run())


def test_item_keeps_the_short_description_and_the_hint_the_step_chain(monkeypatch):
    """Short description on the item; the long step chain goes in the hint."""
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import OptionList, Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.on_option_selected(_selected("session"))
            await pilot.pause()

            options = screen.query_one("#home-options", OptionList)
            labels = [
                str(options.get_option_at_index(index).prompt)
                for index in range(options.option_count)
            ]
            assert "Nova spec · da ideia ao código revisado" in labels
            assert not any("→" in label for label in labels)

            hint = screen.query_one(".home-hint", Static)
            screen.on_option_highlighted(_highlighted("workflow:new-issue"))
            await pilot.pause()
            assert "PRD → Techspec → Tasks → Implementar" in str(hint.render())

            screen.on_option_highlighted(_highlighted("back"))
            await pilot.pause()
            assert str(hint.render()).count("\n") == 1

    asyncio.run(run())


def test_the_sidebar_nests_the_fan_out_items_under_the_step_name():
    """The fan-out step name stays; its tasks are indented below it."""
    from pulse.tui.state import CockpitState

    make_workflow("demo", steps=[("plan", "Planejar"), ("run", "Implementar")])
    state = CockpitState()
    state.configure_workflow("demo")
    state.apply_phase_statuses(
        steps=[
            {"id": "plan", "label": "Planejar"},
            {"id": "run:T1", "label": "Criar o endpoint"},
            {"id": "run:T2", "label": "Montar o CSV"},
        ],
        done_ids=["plan", "run:T1"],
    )

    sidebar = PhaseSidebar(state)
    lines = str(sidebar._render_phases(state)).splitlines()

    assert any(line.strip().endswith("Implementar") for line in lines)
    assert any("T1 · Criar o endpoint" in line for line in lines)
    assert any("T2 · Montar o CSV" in line for line in lines)
    assert any("1/2" in line for line in lines)
    header = next(line for line in lines if line.endswith("Implementar"))
    task = next(line for line in lines if "Criar o endpoint" in line)
    assert _indent(task) > _indent(header)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def test_new_session_lists_pipelines_and_hides_the_generic_loop():
    """`is_default` marks the generic loop, which the menu leaves out."""
    from pulse.store.workflow_defs import list_workflows
    from pulse.tui.screens.home import _session_workflows

    listed = [item.id for item in _session_workflows()]
    everything = {item.id for item in list_workflows()}

    assert "default" in everything, "the generic loop is still in the database"
    assert "default" not in listed
    assert {"new-issue", "quick-fix", "review"} <= set(listed)

    labels = [item.label for item in _session_workflows()]
    assert labels == sorted(labels), "the menu is alphabetical"


def test_loop_with_builtin_task_starts_without_asking_for_text(monkeypatch):
    """Codebase analysis and project setup inspect the repository, not a request.

    Asking for a task description there had no meaningful answer, so Enter
    starts the run immediately.
    """
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Input, Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

            def open_cockpit(self, workflow_id: str, prompt: str) -> None:
                opened.append((workflow_id, prompt))

        opened: list[tuple[str, str]] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.on_option_selected(_selected("session"))
            await pilot.pause()

            screen.on_option_selected(_selected("workflow:analyze-codebase"))
            await pilot.pause()
            assert screen.query_one("#workflow-prompt", Input).display is False

            screen.on_option_selected(_selected("workflow:setup-project"))
            await pilot.pause()
            assert screen.query_one("#workflow-prompt", Input).display is False

            screen.on_option_selected(_selected("workflow:review"))
            await pilot.pause()
            assert screen.query_one("#workflow-prompt", Input).display is False

            assert opened == [
                ("analyze-codebase", "Mapear codebase existente"),
                ("setup-project", "Novo projeto"),
                ("review", "Revisar a branch atual"),
            ]

    asyncio.run(run())


def test_hint_says_enter_starts_these_loops(monkeypatch):
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            screen.on_option_selected(_selected("session"))
            await pilot.pause()

            screen.on_option_highlighted(_highlighted("workflow:analyze-codebase"))
            await pilot.pause()
            hint = str(screen.query_one(".home-hint", Static).render())
            assert "Enter inicia agora" in hint

            screen.on_option_highlighted(_highlighted("workflow:new-issue"))
            await pilot.pause()
            hint = str(screen.query_one(".home-hint", Static).render())
            assert "Enter para descrever a tarefa" in hint

    asyncio.run(run())


def _waiting_run(run_id: str = "run-7", *, held: float = 180.0) -> dict:
    import time

    return {
        "id": run_id,
        "workflow_id": "new-issue",
        "workflow_label": "Nova spec",
        "prompt": "fazer algo",
        "workspace": "/repo",
        "status": "awaiting_input",
        "active": True,
        "awaiting_prompt": True,
        "awaiting_since": time.time() - held,
        "current_step_label": "Especificar",
        "started_at": time.time() - held - 60,
    }


def test_home_announces_the_sessions_waiting_for_the_user(monkeypatch):
    """Leaving the cockpit with an open question must not hide that the run is waiting."""
    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()

            panel = screen.query_one("#home-alerts", Static)
            assert panel.display is False
            assert _home_option_ids(screen) == ["session", "history", "settings", "exit"]

            screen._apply_alerts([_waiting_run()])
            await pilot.pause()
            assert panel.display is True
            text = str(panel.render())
            assert "1 sessão precisa de você" in text
            assert "Nova spec" in text
            assert "Especificar" in text
            assert "há 3min" in text
            assert _home_option_ids(screen)[0] == "alerts"

            screen.on_option_selected(_selected("alerts"))
            await pilot.pause()
            assert _home_option_ids(screen) == ["attach:run-7", "back"]

            screen._apply_alerts([])
            await pilot.pause()
            assert panel.display is False
            assert _home_option_ids(screen) == ["session", "history", "settings", "exit"]

    asyncio.run(run())


def test_home_opens_the_waiting_session_live(monkeypatch):
    """Entering through the alert attaches to the run, where the question is still open."""
    from pathlib import Path as _Path

    class _App:
        def __init__(self) -> None:
            self.opened: list = []

        def open_cockpit(self, workflow_id, prompt, **kwargs):
            self.opened.append((workflow_id, prompt, kwargs))

    class _Screen(HomeScreen):
        fake_app = _App()

        @property
        def app(self):  # type: ignore[override]
            return self.fake_app

    screen = _Screen()
    screen._alerts = [_waiting_run()]
    screen.on_option_selected(_selected("attach:run-7"))

    assert screen.fake_app.opened == [
        (
            "new-issue",
            "fazer algo",
            {"attach_run_id": "run-7", "workspace": _Path("/repo")},
        )
    ]


def test_leaving_the_cockpit_does_not_cancel_the_run():
    """`q` detaches the stream and abandons the prompts; nothing stops the run."""
    make_workflow("demo", steps=[("a", "A")])

    class _Session:
        def __init__(self) -> None:
            self.detached = False
            self.stopped = False

        def detach(self) -> None:
            self.detached = True

        def stop(self) -> bool:
            self.stopped = True
            return True

    class _App:
        def __init__(self) -> None:
            self.popped = 0

        def pop_screen(self) -> None:
            self.popped += 1

    class _Screen(CockpitScreen):
        """Unmounted screen: `action_back_to_menu` does not depend on widgets."""

        fake_app = _App()

        @property
        def app(self):  # type: ignore[override]
            return self.fake_app

    screen = _Screen("demo", "x")
    session = _Session()
    screen._session = session
    screen.state.running = True
    used: list[str] = []
    screen.bridge.abandon = lambda: used.append("abandon")  # type: ignore[method-assign]
    screen.bridge.close = lambda: used.append("close")  # type: ignore[method-assign]

    screen.action_back_to_menu()

    assert session.detached is True
    assert session.stopped is False, "leaving is not stopping"
    assert screen.fake_app.popped == 1
    assert used == ["abandon"]


def test_leaving_before_the_first_step_still_detaches():
    """A run that has not opened a step yet is alive too: leaving detaches, not closes.

    Before the first `phase.begin` (`state.running` still false), leaving closed
    the bridge without detaching, and the orphan session auto-cancelled the run's
    prompts, including those shown by a reattached screen.
    """
    make_workflow("demo", steps=[("a", "A")])

    class _Session:
        detached = False

        def detach(self) -> None:
            self.detached = True

    class _App:
        def pop_screen(self) -> None:
            pass

    class _Screen(CockpitScreen):
        fake_app = _App()

        @property
        def app(self):  # type: ignore[override]
            return self.fake_app

    screen = _Screen("demo", "x")
    session = _Session()
    screen._session = session
    assert screen.state.running is False
    used: list[str] = []
    screen.bridge.abandon = lambda: used.append("abandon")  # type: ignore[method-assign]
    screen.bridge.close = lambda: used.append("close")  # type: ignore[method-assign]

    screen.action_back_to_menu()

    assert session.detached is True
    assert used == ["abandon"]


def test_history_reopens_a_live_run_in_the_cockpit(monkeypatch, tmp_path):
    """An in-progress run the daemon still holds reopens live, not as a page."""
    import pulse.tui.screens.history as history_module
    from pulse.history.models import HistoryItem, HistoryStatus

    item = HistoryItem(
        run_id="run-9",
        workflow_id="new-issue",
        workflow_label="Nova spec",
        title="algo",
        prompt="fazer algo",
        status=HistoryStatus.IN_PROGRESS,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    monkeypatch.setattr(history_module, "active_run_ids", lambda: {"run-9"})

    class _App:
        def __init__(self) -> None:
            self.opened: list = []
            self.pushed: list = []

        def open_cockpit(self, workflow_id, prompt, **kwargs):
            self.opened.append((workflow_id, prompt, kwargs))

        def push_screen(self, screen):
            self.pushed.append(screen)

    class _Screen(history_module.HistoryListScreen):
        fake_app = _App()

        @property
        def app(self):  # type: ignore[override]
            return self.fake_app

    screen = _Screen(workspace=tmp_path)
    screen._items = {"run-9": item}
    screen.on_option_selected(_selected("run-9"))

    assert screen.fake_app.pushed == []
    assert screen.fake_app.opened == [
        (
            "new-issue",
            "fazer algo",
            {"attach_run_id": "run-9", "workspace": tmp_path},
        )
    ]


class _FakeEngineSession:
    """Stands in for `EngineRunSession`: returns `code` or raises `error`."""

    error: Exception | None = None
    code = 0

    def __init__(self, **_kwargs) -> None:
        pass

    def run(self, **_kwargs) -> int:
        if self.error is not None:
            raise self.error
        return self.code


class _ThreadApp:
    """The slice of `App` the run worker calls once the run is over."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.done: list[int] = []

    def call_from_thread(self, callback, code: int) -> None:
        if self.error is not None:
            raise self.error
        self.done.append(code)


def _worker_screen(fake_app: _ThreadApp) -> CockpitScreen:
    make_workflow("demo", steps=[("a", "A")])

    class _Screen(CockpitScreen):
        @property
        def app(self):  # type: ignore[override]
            return fake_app

    return _Screen("demo", "x")


def test_a_run_whose_daemon_is_unreachable_ends_failed_with_the_reason(monkeypatch):
    """The run worker is a thread top-level: a transport error must become the
    run's visible error and exit code 1, never an exception that kills the UI."""
    import httpx

    import pulse.client.run_session as run_session

    class _Unreachable(_FakeEngineSession):
        error = httpx.ConnectError("daemon socket refused")

    monkeypatch.setattr(run_session, "EngineRunSession", _Unreachable)
    fake_app = _ThreadApp()
    screen = _worker_screen(fake_app)

    screen._run_workflow()

    errors = [entry for entry in screen.state.entries if entry.kind == LogKind.ERROR]
    assert [(entry.title, entry.detail) for entry in errors] == [
        ("Workflow falhou", "daemon socket refused")
    ]
    assert screen.state.exit_code == 1
    assert fake_app.done == [1]


def test_a_run_ending_after_the_app_exited_still_records_the_exit_code(monkeypatch):
    """Quitting the app leaves no loop to hand the result to (`RuntimeError`);
    the worker must still finish quietly with the run's state up to date."""
    import pulse.client.run_session as run_session

    monkeypatch.setattr(run_session, "EngineRunSession", _FakeEngineSession)
    screen = _worker_screen(_ThreadApp(RuntimeError("App is not running")))

    screen._run_workflow()

    assert screen._run_over is True
    assert screen.state.exit_code == 0
    assert not [entry for entry in screen.state.entries if entry.kind == LogKind.ERROR]


def test_home_alert_poll_finishing_after_the_app_exited_does_not_crash(monkeypatch):
    """The alert poll runs in a thread; if the app can no longer take its result
    (`call_from_thread` raises `RuntimeError`), the worker ends cleanly instead
    of erroring the whole app."""
    from textual.worker import WorkerState

    import pulse.tui.screens.home as home_module

    monkeypatch.setattr(home_module, "global_config_exists", lambda: True)
    monkeypatch.setattr(home_module, "is_pulse_ready", lambda: True)
    monkeypatch.setattr(home_module, "awaiting_runs", lambda: [_waiting_run()])

    async def run() -> None:
        from textual.app import App, ComposeResult
        from textual.widgets import Static

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield Static("ok")

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = HomeScreen()
            app.push_screen(screen)
            await pilot.pause()
            await app.workers.wait_for_complete()
            screen._apply_alerts([])

            def _app_gone(*_args) -> None:
                raise RuntimeError("App is not running")

            monkeypatch.setattr(app, "call_from_thread", _app_gone)
            screen._poll_alerts()
            await app.workers.wait_for_complete()
            await pilot.pause()

            assert [worker.state for worker in screen.workers] in ([], [WorkerState.SUCCESS])
            assert screen._alerts == []

    asyncio.run(run())


def test_header_labels_follow_state_even_though_watchers_fire_before_compose():
    """Reactive watchers run before `compose` mounts the labels; that first call
    must be a no-op, and later changes must reach the labels."""
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    from pulse.tui.widgets.app_header import AppHeader

    async def run() -> None:
        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def compose(self) -> ComposeResult:
                yield AppHeader()

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            header = app.query_one(AppHeader)
            header.run_label = "RUN 1/3"
            header.workflow_label = "demo"
            await pilot.pause()
            assert str(header.query_one("#run-status", Static).render()) == "RUN 1/3"
            assert str(header.query_one("#workflow-label", Static).render()) == "demo"

    asyncio.run(run())


def test_unmounted_log_stream_has_no_prompt_to_focus():
    """Focusing the prompt before the stream is composed reports `False`, not a crash."""
    from pulse.tui.state import CockpitState

    assert LogStream(CockpitState()).focus_prompt() is False


def test_click_on_an_unmounted_sidebar_is_ignored():
    """A click routed before the sidebar composed its content selects nothing."""
    from textual.events import Click

    from pulse.tui.state import CockpitState

    make_workflow("demo", steps=[("a", "A")])
    state = CockpitState()
    state.configure_workflow("demo")
    sidebar = PhaseSidebar(state)
    posted: list = []
    sidebar.post_message = posted.append  # type: ignore[method-assign]

    sidebar.on_click(Click(sidebar, 1, 1, 0, 0, 1, False, False, False, screen_x=1, screen_y=1))

    assert posted == []
