"""Screens degrade when the daemon cannot be reached: they say so and stay usable.

The TUI is a thin client now, so every read goes through the daemon; a daemon
that does not answer must leave a message on screen, never a crashed app.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.app import App
from textual.widgets import OptionList, Static

from pulse.client.engine_client import EngineClient
from pulse.tui import strings
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.home import HomeScreen
from pulse.tui.screens.settings import SettingsScreen
from pulse.tui.theme import COCKPIT_CSS
from tests.tui.conftest import DAEMON_DOWN, cut_the_daemon


def _run(screen, check) -> None:
    async def run() -> None:
        class Harness(App[None]):
            CSS = COCKPIT_CSS
            notes: list[str] = []

            def on_mount(self) -> None:
                self.push_screen(screen)

            def notify(self, message: str, **_kwargs: object) -> None:
                self.notes.append(message)

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            check(app)

    asyncio.run(run())


def _options(app: App) -> list[str]:
    widget = app.screen.query_one(OptionList)
    return [str(widget.get_option_at_index(i).id) for i in range(widget.option_count)]


@pytest.mark.usefixtures("daemon_down")
def test_settings_says_the_engine_is_down_and_only_offers_back(tmp_path: Path) -> None:
    def check(app: App) -> None:
        report = str(app.screen.query_one("#settings-report", Static).render())
        assert report == strings.ENGINE_UNAVAILABLE.format(error=DAEMON_DOWN)
        assert _options(app) == ["back"]

    _run(SettingsScreen(cwd=tmp_path), check)


@pytest.mark.usefixtures("daemon_down")
def test_history_says_the_engine_is_down_and_lists_nothing(tmp_path: Path) -> None:
    def check(app: App) -> None:
        assert set(app.notes) == {strings.ENGINE_UNAVAILABLE.format(error=DAEMON_DOWN)}
        assert app.screen._items == {}

    _run(HistoryListScreen(workspace=tmp_path), check)


def _hint(app: App) -> str:
    return str(app.screen.query_one(".home-hint", Static).render())


@pytest.mark.usefixtures("daemon_down")
def test_home_offers_to_start_an_engine_that_does_not_answer() -> None:
    """Screens never start the daemon on their own, so Home is where it comes back.

    Hiding every option but the wizard left a daemon stopped mid-session with
    no way back short of relaunching `pulse`.
    """

    def check(app: App) -> None:
        assert _options(app) == ["start_engine", "init", "exit"]
        assert _hint(app) == strings.ENGINE_UNAVAILABLE.format(error=DAEMON_DOWN)

    _run(HomeScreen(), check)


def _choose_start_engine(monkeypatch: pytest.MonkeyPatch, ensure_daemon: object) -> App:
    monkeypatch.setattr(EngineClient, "ensure_daemon", ensure_daemon)

    async def run() -> App:
        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HomeScreen())

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            app.screen.query_one(OptionList).highlighted = 0
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            app.options = _options(app)  # type: ignore[attr-defined]  # read after exit
            app.hint = _hint(app)  # type: ignore[attr-defined]  # read after exit
        return app

    return asyncio.run(run())


def test_starting_the_engine_from_home_brings_the_menu_back(
    monkeypatch: pytest.MonkeyPatch, in_process_daemon: object
) -> None:
    cut_the_daemon(monkeypatch)

    def come_back(_self: EngineClient, **_kwargs: object) -> None:
        monkeypatch.setattr(EngineClient, "_http", lambda _client: in_process_daemon)

    app = _choose_start_engine(monkeypatch, come_back)

    assert "start_engine" not in app.options  # type: ignore[attr-defined]  # set by the run
    assert app.hint == strings.HOME_ROOT_HINT  # type: ignore[attr-defined]  # set by the run


def test_an_engine_that_will_not_start_says_why_and_offers_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cut_the_daemon(monkeypatch)

    def give_up(_self: EngineClient, **_kwargs: object) -> None:
        raise RuntimeError("could not connect to pulse-engine")

    app = _choose_start_engine(monkeypatch, give_up)

    assert app.options == ["start_engine", "init", "exit"]  # type: ignore[attr-defined]  # set by the run
    assert app.hint == strings.ENGINE_UNAVAILABLE.format(  # type: ignore[attr-defined]  # set by the run
        error="could not connect to pulse-engine"
    )


def test_settings_going_back_from_a_picker_reports_a_daemon_gone_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, in_process_daemon: object
) -> None:
    """Going back redraws the previous menu from the daemon; losing it while a picker
    is open must leave a message, not a traceback.
    """

    async def run() -> None:
        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(SettingsScreen(cwd=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            screen._show_global_fields()
            screen._show_permissions()
            await pilot.pause()

            cut_the_daemon(monkeypatch)
            await pilot.press("escape")
            await pilot.pause()

            report = str(screen.query_one("#settings-report", Static).render())
            assert report == strings.ENGINE_UNAVAILABLE.format(error=DAEMON_DOWN)
            assert app.screen is screen

        assert app.return_code is None

    asyncio.run(run())
