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


@pytest.mark.usefixtures("daemon_down")
def test_home_offers_the_setup_when_it_cannot_tell_the_machine_is_ready() -> None:
    """Without an answer, the safe offer is the wizard, which explains the failure itself."""

    def check(app: App) -> None:
        assert _options(app) == ["init", "exit"]

    _run(HomeScreen(), check)


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
