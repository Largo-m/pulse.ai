"""The pointer menu shared by the settings screen and the new-session picker."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult

from pulse.tui.menu_rows import POINTER, MenuRow
from pulse.tui.widgets.menu_list import MenuList

ROWS = [MenuRow("a", "Alfa"), MenuRow("b", "Beta", current=True), MenuRow("c", "Gama")]


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield MenuList(id="menu")


def _pointed_rows(menu: MenuList) -> list[str]:
    """Ids of every row drawn with the pointer: exactly one when the menu is right."""
    return [
        str(menu.get_option_at_index(index).id)
        for index in range(menu.option_count)
        if menu.get_option_at_index(index).prompt.plain.startswith(POINTER)
    ]


def _run(scenario) -> None:
    async def body() -> None:
        app = _Harness()
        async with app.run_test(size=(60, 12)) as pilot:
            menu = app.query_one(MenuList)
            menu.focus()
            await scenario(pilot, menu)

    asyncio.run(body())


def test_a_fresh_menu_points_at_the_current_choice():
    seen: list[object] = []

    async def scenario(pilot, menu: MenuList) -> None:
        menu.show_rows(ROWS)
        await pilot.pause()
        seen.extend([menu.highlighted, _pointed_rows(menu), menu.pointed])

    _run(scenario)
    assert seen == [1, ["b"], ROWS[1]]


def test_moving_the_cursor_moves_the_only_pointer():
    """The old row loses the pointer as the new one gains it: never two, never none."""
    seen: list[list[str]] = []

    async def scenario(pilot, menu: MenuList) -> None:
        menu.show_rows(ROWS)
        await pilot.press("down")
        await pilot.pause()
        seen.append(_pointed_rows(menu))
        await pilot.press("up", "up")
        await pilot.pause()
        seen.append(_pointed_rows(menu))

    _run(scenario)
    assert seen == [["c"], ["a"]]


def test_a_redraw_of_the_same_menu_keeps_the_pointer_where_it_was():
    seen: list[list[str]] = []

    async def scenario(pilot, menu: MenuList) -> None:
        menu.show_rows(ROWS)
        await pilot.press("down")
        await pilot.pause()
        menu.show_rows(ROWS)
        await pilot.pause()
        seen.append(_pointed_rows(menu))

    _run(scenario)
    assert seen == [["c"]]


def test_an_explicit_focus_wins_and_an_unknown_one_falls_back():
    """`focus` names the row a menu returns to; a stale id must not leave the menu blank."""
    seen: list[list[str]] = []

    async def scenario(pilot, menu: MenuList) -> None:
        menu.show_rows(ROWS, focus="a")
        await pilot.pause()
        seen.append(_pointed_rows(menu))
        menu.show_rows([MenuRow("x", "Xis"), MenuRow("y", "Ipsilon")], focus="gone")
        await pilot.pause()
        seen.append(_pointed_rows(menu))

    _run(scenario)
    assert seen == [["a"], ["x"]]


def test_an_empty_menu_points_at_nothing():
    seen: list[object] = []

    async def scenario(pilot, menu: MenuList) -> None:
        menu.show_rows([])
        await pilot.pause()
        seen.extend([menu.option_count, menu.pointed])

    _run(scenario)
    assert seen == [0, None]
