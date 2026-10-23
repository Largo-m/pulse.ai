from __future__ import annotations

from pathlib import Path

from textual.app import App

from pulse.client.protocol import RunForm
from pulse.tui import strings
from pulse.tui.screens.cockpit import CockpitScreen
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.home import HomeScreen
from pulse.tui.screens.onboarding import OnboardingScreen
from pulse.tui.screens.settings import SettingsScreen
from pulse.tui.theme import COCKPIT_CSS


class PulseApp(App[None]):
    CSS = COCKPIT_CSS
    TITLE = strings.APP_TITLE

    def on_mount(self) -> None:
        self.push_screen(HomeScreen())

    def open_cockpit(
        self,
        workflow_id: str,
        user_prompt: str,
        *,
        resume_run_id: str | None = None,
        attach_run_id: str | None = None,
        workspace: Path | None = None,
        branch: str = "",
        form: RunForm | None = None,
    ) -> None:
        self.push_screen(
            CockpitScreen(
                workflow_id,
                user_prompt,
                workspace=workspace,
                resume_run_id=resume_run_id,
                attach_run_id=attach_run_id,
                branch=branch,
                form=form,
            )
        )

    def open_history(self) -> None:
        self.push_screen(HistoryListScreen())

    def open_settings(self) -> None:
        self.push_screen(SettingsScreen())

    def open_onboarding(self, *, force: bool = False) -> None:
        def _done(result: int | None) -> None:
            if self.screen_stack and isinstance(self.screen, HomeScreen):
                self.screen._refresh_options()

        self.push_screen(OnboardingScreen(force=force), callback=_done)


def run_pulse_app() -> int:
    app = PulseApp()
    app.run()
    return 0


def run_onboarding_app(*, force: bool = False) -> int:
    class OnboardApp(App[int]):
        CSS = COCKPIT_CSS
        TITLE = strings.ONBOARDING_APP_TITLE

        def on_mount(self) -> None:
            def _done(result: int | None) -> None:
                self.exit(result if result is not None else 0)

            self.push_screen(OnboardingScreen(force=force), callback=_done)

    app = OnboardApp()
    return int(app.run() or 0)
