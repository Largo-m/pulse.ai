"""The task box: Enter sends, every line-break gesture edits instead of sending."""

from __future__ import annotations

import asyncio

import pytest
from textual import events
from textual.app import App, ComposeResult
from textual.pilot import Pilot

from pulse.tui.widgets.task_composer import TaskComposer


class _Harness(App[None]):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []

    def compose(self) -> ComposeResult:
        yield TaskComposer(id="composer")

    def on_task_composer_submitted(self, event: TaskComposer.Submitted) -> None:
        self.sent.append(event.text)


async def _type(pilot: Pilot[None], text: str) -> None:
    keys = {" ": "space", "\\": "backslash"}
    await pilot.press(*(keys.get(char, char) for char in text))


def test_enter_sends_the_typed_text():
    async def run() -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await _type(pilot, "fix login")
            await pilot.press("enter")
            await pilot.pause()
            assert app.sent == ["fix login"]

    asyncio.run(run())


@pytest.mark.parametrize("key", ["ctrl+j", "shift+enter", "alt+enter"])
def test_line_break_keys_edit_the_task_instead_of_sending_it(key):
    """Shift/Alt+Enter depend on the terminal; Ctrl+J reaches the app everywhere."""

    async def run() -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await _type(pilot, "ab")
            await pilot.press(key)
            await _type(pilot, "cd")
            await pilot.pause()
            assert app.query_one(TaskComposer).text == "ab\ncd"
            assert app.sent == []

    asyncio.run(run())


def test_a_trailing_backslash_turns_enter_into_a_line_break():
    """The portable gesture agent CLIs teach: the backslash is consumed, not kept."""

    async def run() -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await _type(pilot, "first\\")
            await pilot.press("enter")
            await _type(pilot, "second")
            await pilot.press("enter")
            await pilot.pause()
            assert app.sent == ["first\nsecond"]

    asyncio.run(run())


def test_a_backslash_inside_the_line_does_not_hold_back_enter():
    """Only a backslash right before the cursor continues the line."""

    async def run() -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            await _type(pilot, "a\\b")
            await pilot.press("enter")
            await pilot.pause()
            assert app.sent == ["a\\b"]

    asyncio.run(run())


def test_pasted_lines_are_sent_as_they_were_pasted():
    """A stack trace pasted as the task keeps its lines; an `Input` flattened them."""

    async def run() -> None:
        app = _Harness()
        async with app.run_test() as pilot:
            trace = "Traceback:\n  File app.py, line 3\nKeyError: 'id'"
            # Terminals deliver a paste to the app, which forwards it to the focus.
            app.post_message(events.Paste(trace))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.sent == [trace]

    asyncio.run(run())
