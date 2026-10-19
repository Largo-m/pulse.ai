"""The branch name is confirmed before a worktree run starts."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pulse.tui import engine, strings
from pulse.tui.screens.branch_name import BranchNameScreen
from pulse.tui.theme import COCKPIT_CSS


def test_confirming_a_free_name_returns_it_and_the_refusals_stay_on_screen(
    tmp_path: Path, monkeypatch
) -> None:
    answers = iter(
        [
            (False, False),
            (True, True),
            engine.EngineUnavailable("sem daemon"),
            (True, False),
        ]
    )

    def _check(_workspace: Path, _name: str) -> tuple[bool, bool]:
        answer = next(answers)
        if isinstance(answer, engine.EngineError):
            raise answer
        return answer

    monkeypatch.setattr(engine, "branch_check", _check)

    async def run() -> None:
        from textual.app import App
        from textual.widgets import Input, Static

        chosen: list[str | None] = []

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(
                    BranchNameScreen(suggested="corrigir-o-login", workspace=tmp_path),
                    chosen.append,
                )

        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, BranchNameScreen)
            name = screen.query_one("#branch-name", Input)
            hint = screen.query_one("#branch-hint", Static)

            name.value = "   "
            screen._confirm()
            assert str(hint.render()) == strings.BRANCH_EMPTY

            name.value = "nome ruim"
            screen._confirm()
            assert str(hint.render()) == strings.BRANCH_INVALID

            name.value = "ja-existe"
            screen._confirm()
            assert str(hint.render()) == strings.BRANCH_TAKEN

            name.value = "corrigir-o-login"
            screen._confirm()
            assert "sem daemon" in str(hint.render())

            screen.on_name_submitted(Input.Submitted(name, name.value))
            await pilot.pause()
            assert chosen == ["corrigir-o-login"]

    asyncio.run(run())
