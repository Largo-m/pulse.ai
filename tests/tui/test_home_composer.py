"""Home task box: it replaces the menu, grows with the task and starts only real tasks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from textual.app import App, ComposeResult
from textual.widgets import OptionList, Static

from pulse.tui.screens.home import HomeScreen
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.task_composer import TaskComposer
from tests.conftest import onboard_machine

# Mirrors the cap in `home_theme.py`: past it the box scrolls instead of
# pushing the hint off a 24-row terminal.
COMPOSER_MAX_ROWS = 12
COMPOSER_MIN_ROWS = 3


class _Harness(App[None]):
    CSS = COCKPIT_CSS

    def __init__(self) -> None:
        super().__init__()
        self.opened: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Static("ok")

    def open_cockpit(self, workflow_id: str, prompt: str) -> None:
        self.opened.append((workflow_id, prompt))


def _select(screen: HomeScreen, option_id: str) -> None:
    screen.on_option_selected(SimpleNamespace(option_id=option_id))


async def _open_composer(app: _Harness, pilot) -> HomeScreen:
    screen = HomeScreen()
    app.push_screen(screen)
    await pilot.pause()
    _select(screen, "session")
    _select(screen, "workflow:quick-fix")
    await pilot.pause()
    return screen


def test_the_task_box_takes_the_menu_place_under_the_workflow_name():
    """The chosen workflow titles the box, so the user knows what Enter will start."""
    onboard_machine()

    async def run() -> None:
        app = _Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_composer(app, pilot)

            assert screen.query_one("#home-options", OptionList).display is False
            assert screen.query_one(".home-hint", Static).display is False
            title = screen.query_one("#composer-title", Static)
            assert str(title.render()) == "Correção rápida"
            assert screen.query_one("#workflow-prompt", TaskComposer).has_focus

            await pilot.press("escape")
            await pilot.pause()
            assert screen.query_one("#task-composer").display is False
            assert screen.query_one("#home-options", OptionList).has_focus

    asyncio.run(run())


def test_a_blank_task_keeps_the_box_open_and_starts_nothing():
    onboard_machine()

    async def run() -> None:
        app = _Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_composer(app, pilot)
            screen.query_one("#workflow-prompt", TaskComposer).text = "  \n "
            await pilot.press("enter")
            await pilot.pause()

            assert app.opened == []
            assert screen.query_one("#task-composer").display is True

    asyncio.run(run())


def test_a_multi_line_task_starts_the_run_with_its_lines():
    onboard_machine()

    async def run() -> None:
        app = _Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_composer(app, pilot)
            screen.query_one("#workflow-prompt", TaskComposer).text = "login falha\n\nerro 500"
            await pilot.press("enter")
            await pilot.pause()

            assert app.opened == [("quick-fix", "login falha\n\nerro 500")]

    asyncio.run(run())


def test_esc_discards_the_draft_so_the_next_workflow_starts_blank():
    onboard_machine()

    async def run() -> None:
        app = _Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_composer(app, pilot)
            composer = screen.query_one("#workflow-prompt", TaskComposer)
            composer.text = "rascunho"
            await pilot.press("escape")
            _select(screen, "workflow:new-issue")
            await pilot.pause()

            assert composer.text == ""
            assert str(screen.query_one("#composer-title", Static).render()) == "Nova spec"

    asyncio.run(run())


def test_the_box_grows_with_the_task_up_to_a_cap():
    """Roomy from the start, taller per line, and capped so the hint stays on screen."""
    onboard_machine()

    async def run() -> None:
        app = _Harness()
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_composer(app, pilot)
            composer = screen.query_one("#workflow-prompt", TaskComposer)
            assert composer.size.height == COMPOSER_MIN_ROWS

            composer.text = "\n".join(f"line {n}" for n in range(6))
            await pilot.pause()
            assert composer.size.height == 6

            composer.text = "\n".join(f"line {n}" for n in range(40))
            await pilot.pause()
            assert composer.size.height == COMPOSER_MAX_ROWS
            assert screen.query_one(".composer-hint", Static).region.bottom <= 40

    asyncio.run(run())
