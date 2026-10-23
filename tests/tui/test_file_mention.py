"""`@` in the task box: which token is a mention, which files match it, how one is picked.

The mention is plain text for the agent; Pulse only helps type a real path.
A false trigger (an e-mail, a finished mention) would hijack Enter, which
sends the task, so the trigger rules are pinned in both directions.
"""

from __future__ import annotations

import asyncio

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot

from pulse.tui.widgets.file_mention import FileMentionList, match_files, mention_at
from pulse.tui.widgets.task_composer import TaskComposer

FILES = ["README.md", "docs/readme-pt.md", "pulse/tui/app.py", "pulse/tui/widgets/task_form.py"]


@pytest.mark.parametrize(
    ("before_cursor", "query"),
    [
        ("@", ""),
        ("@tui", "tui"),
        ("veja @pulse/tui", "pulse/tui"),
        ("primeira linha\n@doc", "doc"),
        ("a\t@x", "x"),
    ],
)
def test_an_at_sign_at_a_word_start_opens_a_mention(before_cursor: str, query: str) -> None:
    assert mention_at(before_cursor) == query


@pytest.mark.parametrize(
    "before_cursor",
    ["", "sem menção", "fale com dev@empresa.com", "@README.md ", "@a b"],
)
def test_text_without_an_open_mention_is_left_alone(before_cursor: str) -> None:
    assert mention_at(before_cursor) is None


def test_an_empty_query_offers_the_first_files_in_order() -> None:
    assert match_files(FILES, "", limit=2) == ["README.md", "docs/readme-pt.md"]


def test_a_file_name_match_ranks_above_a_folder_match() -> None:
    """Typing `app` means the file named so, not every file under an `app/` folder."""
    files = ["app/main.py", "pulse/tui/app.py", "lib/my_app.py"]

    assert match_files(files, "app") == ["pulse/tui/app.py", "lib/my_app.py", "app/main.py"]


def test_matching_ignores_case_and_drops_files_that_do_not_match() -> None:
    assert match_files(FILES, "README") == ["README.md", "docs/readme-pt.md"]
    assert match_files(FILES, "nada") == []


def test_the_list_is_capped() -> None:
    files = [f"src/file_{index}.py" for index in range(20)]

    assert match_files(files, "file", limit=8) == files[:8]


class _Harness(App[None]):
    def __init__(self, files: list[str]) -> None:
        super().__init__()
        self.files = files
        self.sent: list[str] = []

    def compose(self) -> ComposeResult:
        yield TaskComposer(id="composer")
        yield FileMentionList(id="mentions")

    def on_mount(self) -> None:
        picker = self.query_one(FileMentionList)
        picker.set_files(self.files)
        self.query_one(TaskComposer).bind_mentions(picker)

    def on_task_composer_submitted(self, event: TaskComposer.Submitted) -> None:
        self.sent.append(event.text)


async def _type(pilot: Pilot[None], text: str) -> None:
    keys = {" ": "space", "@": "at", "/": "slash", ".": "full_stop"}
    await pilot.press(*(keys.get(char, char) for char in text))
    await pilot.pause()


def _shown(app: _Harness) -> list[str]:
    picker = app.query_one(FileMentionList)
    if not picker.display:
        return []
    return [str(picker.get_option_at_index(i).id) for i in range(picker.option_count)]


def _drive(test, files: list[str] = FILES) -> None:
    async def body() -> None:
        app = _Harness(files)
        async with app.run_test() as pilot:
            await test(app, pilot)

    asyncio.run(body())


def test_typing_at_lists_the_workspace_files_and_typing_more_filters_them() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        assert _shown(app) == []
        await _type(pilot, "veja @")
        assert _shown(app) == FILES
        await _type(pilot, "form")
        assert _shown(app) == ["pulse/tui/widgets/task_form.py"]

    _drive(test)


def test_enter_on_an_open_list_inserts_the_path_instead_of_sending() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        await _type(pilot, "veja @tui")
        await pilot.press("down", "enter")
        await pilot.pause()

        assert app.query_one(TaskComposer).text == "veja @pulse/tui/widgets/task_form.py "
        assert app.sent == []
        assert _shown(app) == []

        await pilot.press("enter")
        await pilot.pause()
        assert app.sent == ["veja @pulse/tui/widgets/task_form.py "]

    _drive(test)


def test_tab_picks_the_highlighted_file_too() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        await _type(pilot, "@readme")
        await pilot.press("tab")
        await pilot.pause()

        assert app.query_one(TaskComposer).text == "@README.md "

    _drive(test)


def test_escape_closes_the_list_and_enter_then_sends() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        await _type(pilot, "@app")
        await pilot.press("escape")
        await pilot.pause()
        assert _shown(app) == []
        assert app.query_one(TaskComposer).has_focus

        await pilot.press("enter")
        await pilot.pause()
        assert app.sent == ["@app"]

    _drive(test)


def test_a_query_with_no_match_hides_the_list_and_keeps_enter_sending() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        await _type(pilot, "@zzz")
        assert _shown(app) == []

        await pilot.press("enter")
        await pilot.pause()
        assert app.sent == ["@zzz"]

    _drive(test)


def test_clicking_a_file_inserts_it() -> None:
    async def test(app: _Harness, pilot: Pilot[None]) -> None:
        await _type(pilot, "@pulse")
        # Row 1 is the first option: the list's default border takes row 0.
        await pilot.click(FileMentionList, offset=(2, 1))
        await pilot.pause()

        assert app.query_one(TaskComposer).text == "@pulse/tui/app.py "
        assert app.query_one(TaskComposer).has_focus

    _drive(test)
