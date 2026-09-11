from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse import __version__
from pulse.config import global_config_exists
from pulse.plan.spec_types import SPEC_TYPES
from pulse.terminal.welcome import BANNER, PULSE_LINE, PULSE_WAVE, is_pulse_ready


def _home_brand() -> str:
    logo_lines = BANNER.strip("\n").splitlines()
    wave_lines = (PULSE_LINE, PULSE_WAVE)
    width = max(len(line) for line in (*logo_lines, *wave_lines))
    parts = [line.ljust(width) for line in (*logo_lines, *wave_lines)]
    return "\n".join(parts)


_HOME_BRAND = _home_brand()


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static(_HOME_BRAND, classes="home-brand")
            yield Static(
                f"Orquestrador de workflows · v{__version__}",
                classes="home-sub",
            )
            yield OptionList(id="home-options")
            yield Static("Enter seleciona · Q sai", classes="home-hint")
            yield Input(
                placeholder="Descreva a tarefa…",
                id="workflow-prompt",
                classes="-hidden",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._pending_workflow: str | None = None
        self._refresh_options()
        self.query_one("#workflow-prompt", Input).display = False

    def _refresh_options(self) -> None:
        options = self.query_one("#home-options", OptionList)
        options.clear_options()
        ready = is_pulse_ready()
        if not global_config_exists():
            options.add_option(Option("Configurar Pulse", id="init"))
            options.add_option(Option("Sair", id="exit"))
            return
        if ready:
            for spec in SPEC_TYPES:
                options.add_option(
                    Option(f"{spec.label} — {spec.description}", id=f"workflow:{spec.id}")
                )
        else:
            options.add_option(Option("Configurar Pulse", id="init"))
        options.add_option(Option("Histórico — Issues e fixes", id="history"))
        options.add_option(Option("Configurações", id="settings"))
        options.add_option(Option("Sair", id="exit"))

    @on(OptionList.OptionSelected, "#home-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        action = str(option_id)
        if action == "exit":
            self.app.exit()
            return
        if action == "init":
            self._run_init()
            return
        if action == "settings":
            self._run_settings()
            return
        if action == "history":
            self.app.open_history()
            return
        if action.startswith("workflow:"):
            workflow_id = action.split(":", 1)[1]
            if workflow_id in {"setup-project", "analyze-codebase"}:
                self.app.open_cockpit(workflow_id, default_prompt(workflow_id))
                return
            self._pending_workflow = workflow_id
            prompt_input = self.query_one("#workflow-prompt", Input)
            prompt_input.display = True
            prompt_input.focus()
            if workflow_id == "fix-bug":
                prompt_input.placeholder = "Descreva a quick task…"
            else:
                prompt_input.placeholder = "Descreva o que deseja construir…"

    @on(Input.Submitted, "#workflow-prompt")
    def on_prompt_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        workflow_id = self._pending_workflow
        event.input.value = ""
        event.input.display = False
        self._pending_workflow = None
        if not workflow_id or not text:
            return
        self.app.open_cockpit(workflow_id, text)

    def action_quit_app(self) -> None:
        self.app.exit()

    def _run_external(self, callback: Callable[[], object]) -> None:
        from concurrent.futures import ThreadPoolExecutor

        from textual.app import SuspendNotSupported

        def _run() -> None:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(callback).result()

        try:
            with self.app.suspend():
                _run()
        except SuspendNotSupported:
            _run()
        self._refresh_options()

    def _run_init(self) -> None:
        from pulse.onboarding import run_onboarding_wizard

        self._run_external(run_onboarding_wizard)

    def _run_settings(self) -> None:
        from pulse.terminal.settings_menu import run_settings_menu

        self._run_external(run_settings_menu)


def default_prompt(workflow_id: str) -> str:
    if workflow_id == "setup-project":
        return "Novo projeto"
    if workflow_id == "analyze-codebase":
        return "Mapear codebase existente"
    return ""
