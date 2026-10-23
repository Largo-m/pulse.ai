"""The history list behaves like an agent CLI session picker.

Search and list work together: typing filters, the arrows and Enter keep
driving the list from the search box, Esc steps back one level at a time, and
the screen always says what to do next.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from textual.app import App
from textual.widgets import Input, OptionList, Static

from pulse.domain.run import StepRecord, StepStatus
from pulse.history.catalog import HistoryCatalog
from pulse.store import runs as run_store
from pulse.tui import strings
from pulse.tui.history_rows import POINTER
from pulse.tui.hydrate import hydrate_history_item
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.theme import COCKPIT_CSS
from tests.conftest import make_workflow, store_run_status, store_step


def _finished_run(workspace: Path, run_id: str, prompt: str) -> None:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt=prompt,
        steps=[StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester")],
    )
    step = record.steps[0]
    step.status = StepStatus.DONE
    store_step(record.id, step)
    store_run_status(record.id, "completed")


class _Harness(App[None]):
    CSS = COCKPIT_CSS

    def __init__(self, workspace: Path) -> None:
        super().__init__()
        self._workspace = workspace

    def on_mount(self) -> None:
        self.push_screen(HistoryListScreen(workspace=self._workspace))


def _drive(workspace: Path, scenario: Callable[[App[None], object], Awaitable[None]]) -> None:
    async def run() -> None:
        app = _Harness(workspace)
        async with app.run_test(size=(110, 32)) as pilot:
            await pilot.pause()
            await scenario(app, pilot)

    asyncio.run(run())


def _pointed_titles(screen: HistoryListScreen) -> list[str]:
    options = screen.query_one("#history-options", OptionList)
    lines = [
        str(options.get_option_at_index(index).prompt).splitlines()[0]
        for index in range(options.option_count)
    ]
    return [line for line in lines if line.startswith(POINTER)]


def _text(screen: HistoryListScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


def test_the_pointer_marks_exactly_the_run_under_the_cursor(tmp_path: Path) -> None:
    _finished_run(tmp_path, "run-old", "Primeira tarefa")
    _finished_run(tmp_path, "run-new", "Segunda tarefa")

    async def scenario(app: App[None], pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        first = screen._highlighted()
        assert first is not None
        assert _pointed_titles(screen) == [f"{POINTER} ✓ {first.title}"]

        await pilot.press("down")
        await pilot.pause()

        second = screen._highlighted()
        assert second is not None
        assert second.item_id != first.item_id
        assert _pointed_titles(screen) == [f"{POINTER} ✓ {second.title}"]

    _drive(tmp_path, scenario)


def test_arrows_and_enter_in_the_search_drive_the_list(tmp_path: Path) -> None:
    """Filtering and picking never needs a focus switch, as in agent CLI pickers."""
    _finished_run(tmp_path, "run-a", "Ajustar login")
    _finished_run(tmp_path, "run-b", "Ajustar logout")
    _finished_run(tmp_path, "run-c", "Outra coisa")

    async def scenario(app: App[None], pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        await pilot.press("slash", *"ajustar")
        await pilot.pause()
        assert isinstance(screen.focused, Input)
        assert set(screen._items) == {"run-a", "run-b"}

        start = screen._highlighted()
        await pilot.press("down")
        await pilot.pause()
        target = screen._highlighted()
        assert start is not None
        assert target is not None
        assert target.item_id != start.item_id
        assert isinstance(screen.focused, Input), "the arrows did not steal the focus"

        await pilot.press("enter")
        await pilot.pause()

        assert isinstance(app.screen, HistoryDetailScreen)
        assert app.screen.item.run_id == target.item_id

    _drive(tmp_path, scenario)


def test_escape_leaves_the_search_one_step_at_a_time(tmp_path: Path) -> None:
    """Esc clears the query, then returns to the list, and only then leaves."""
    _finished_run(tmp_path, "run-a", "Ajustar login")

    async def scenario(app: App[None], pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        search = screen.query_one("#history-search", Input)
        await pilot.press("slash", *"xyz")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()
        assert search.value == ""
        assert screen.focused is search

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(screen.focused, OptionList)
        assert app.screen is screen

        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is not screen

    _drive(tmp_path, scenario)


def test_an_empty_history_says_how_to_start(tmp_path: Path) -> None:
    async def scenario(app: App[None], _pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        assert _text(screen, "#history-empty") == (
            f"{strings.HISTORY_EMPTY}\n{strings.HISTORY_EMPTY_ACTION}"
        )
        assert screen.query_one("#history-options").display is False
        assert strings.HISTORY_COUNT_MANY.format(count=0) in _text(screen, "#history-header")

    _drive(tmp_path, scenario)


def test_a_search_without_matches_names_the_query_and_the_way_out(tmp_path: Path) -> None:
    """The header drops the run count while searching: zero matches is not zero runs."""
    _finished_run(tmp_path, "run-a", "Ajustar login")

    async def scenario(app: App[None], pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        await pilot.press("slash", *"xyz")
        await pilot.pause()

        assert _text(screen, "#history-empty") == (
            f"{strings.HISTORY_NO_MATCH.format(query='xyz')}\n{strings.HISTORY_NO_MATCH_ACTION}"
        )
        header = _text(screen, "#history-header")
        assert strings.HISTORY_COUNT_MANY.format(count=0) not in header
        assert tmp_path.name in header

    _drive(tmp_path, scenario)


def test_the_key_line_follows_the_focus(tmp_path: Path) -> None:
    """`d remover` is only offered where `d` removes; in the search it types."""
    _finished_run(tmp_path, "run-a", "Ajustar login")

    async def scenario(app: App[None], pilot) -> None:
        screen = app.screen
        assert isinstance(screen, HistoryListScreen)
        assert "d remover" in _text(screen, "#history-keys")

        await pilot.press("slash")
        await pilot.pause()

        keys = _text(screen, "#history-keys")
        assert "d remover" not in keys
        assert "esc sair da busca" in keys

    _drive(tmp_path, scenario)


def test_a_reopened_run_names_itself_in_the_header(tmp_path: Path) -> None:
    """Phase titles take over the stream heading, so the header is what says which run this is."""
    _finished_run(tmp_path, "run-a", "Ajustar login\ncom detalhes")
    item = HistoryCatalog(tmp_path).get("run-a")
    assert item is not None

    state = hydrate_history_item(item, tmp_path, None)

    assert state.workflow_label == f"DEMO · {' '.join(item.title.split())}"
