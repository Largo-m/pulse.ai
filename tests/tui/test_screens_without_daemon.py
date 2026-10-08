"""Screens degrade when the daemon cannot be reached: they say so and stay usable.

The TUI is a thin client now, so every read goes through the daemon; a daemon
that will not start must leave a message on screen, never a crashed app.
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

REFUSED = "could not connect to pulse-engine"


@pytest.fixture
def daemon_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_self: object) -> None:
        raise RuntimeError(REFUSED)

    monkeypatch.setattr(EngineClient, "ensure_daemon", refuse)


def _run(screen, check) -> None:
    async def run() -> None:
        class Harness(App[None]):
            CSS = COCKPIT_CSS
            notes: list[str] = []

            def on_mount(self) -> None:
                self.push_screen(screen)

            def notify(self, message: str, **_kwargs: object) -> None:  # type: ignore[override]  # records instead of toasting
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
        assert report == strings.ENGINE_UNAVAILABLE.format(error=REFUSED)
        assert _options(app) == ["back"]

    _run(SettingsScreen(cwd=tmp_path), check)


@pytest.mark.usefixtures("daemon_down")
def test_history_says_the_engine_is_down_and_lists_nothing(tmp_path: Path) -> None:
    def check(app: App) -> None:
        assert set(app.notes) == {strings.ENGINE_UNAVAILABLE.format(error=REFUSED)}
        assert app.screen._items == {}

    _run(HistoryListScreen(workspace=tmp_path), check)


@pytest.mark.usefixtures("daemon_down")
def test_home_offers_the_setup_when_it_cannot_tell_the_machine_is_ready() -> None:
    """Without an answer, the safe offer is the wizard, which explains the failure itself."""

    def check(app: App) -> None:
        assert _options(app) == ["init", "exit"]

    _run(HomeScreen(), check)
