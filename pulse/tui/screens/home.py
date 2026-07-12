from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse import __version__
from pulse.config import global_config_exists
from pulse.plan.spec_types import SPEC_TYPES
from pulse.terminal.welcome import is_pulse_ready


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("PULSE // ACP COCKPIT", classes="home-brand")
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
            self.app.run_worker(self._run_init, exclusive=True, thread=True)
            return
        if action == "settings":
            self.app.run_worker(self._run_settings, exclusive=True, thread=True)
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

    def _run_init(self) -> None:
        from pulse.onboarding import run_onboarding_wizard

        run_onboarding_wizard()
        self.app.call_from_thread(self._refresh_options)

    def _run_settings(self) -> None:
        from pulse.terminal.settings_menu import run_settings_menu

        run_settings_menu()
        self.app.call_from_thread(self._refresh_options)


def default_prompt(workflow_id: str) -> str:
    if workflow_id == "setup-project":
        return "Novo projeto"
    if workflow_id == "analyze-codebase":
        return "Mapear codebase existente"
    return ""
