from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("textual")

from pulse.tui.screens.onboarding import OnboardingScreen
from pulse.tui.theme import COCKPIT_CSS


def test_onboarding_uses_centered_panel_layout():
    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(OnboardingScreen())

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, OnboardingScreen)
            title = screen.query_one(".onboard-title")
            assert "CONFIGURAR PULSE" in str(title.render())
            assert screen.query_one("#onboard-options")
            assert screen.query_one("#onboard-input")
            assert screen.query_one("#onboard-report")

    asyncio.run(run())
