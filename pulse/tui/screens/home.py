from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from pulse import __version__
from pulse.brand import BANNER, PULSE_LINE, PULSE_WAVE
from pulse.client.active_runs import active_runs, awaiting_runs, held_tail, run_line
from pulse.config import global_config_exists
from pulse.status_labels import status_color, status_icon
from pulse.store.workflow_defs import list_workflows
from pulse.runtime.ready import is_pulse_ready


def _home_brand() -> str:
    logo_lines = BANNER.strip("\n").splitlines()
    wave_lines = (PULSE_LINE, PULSE_WAVE)
    width = max(len(line) for line in (*logo_lines, *wave_lines))
    parts = [line.ljust(width) for line in (*logo_lines, *wave_lines)]
    return "\n".join(parts)


_HOME_BRAND = _home_brand()


def _session_workflows() -> list:
    """Workflows offered by "Nova sessão": the pipelines, sorted by label.

    The generic loop (`is_default`) is hidden from this menu only; it remains
    available in the database and the daemon API.
    """
    return sorted(
        (item for item in list_workflows() if not item.is_default),
        key=lambda item: item.label,
    )


ROOT = "root"
SESSION = "session"
ALERTS = "alerts"

ALERT_POLL_SECONDS = 3.0

ROOT_HINT = "↑↓ navega · Enter seleciona · Q sai"
TASK_PLACEHOLDER = "Descreva a tarefa e tecle Enter · Esc cancela"


def _alert_panel(runs: list[dict[str, Any]]) -> Text:
    """Alert panel listing how many sessions are waiting and which ones.

    One line per session, not just a count, so the user can tell which run needs them.
    """
    tone = status_color("awaiting_input")
    count = len(runs)
    noun = "sessão precisa" if count == 1 else "sessões precisam"
    panel = Text()
    panel.append(f"{status_icon('awaiting_input')} {count} {noun} de você", style=tone)
    for run in runs:
        panel.append(f"\n   {run_line(run, tail=held_tail(run))}", style="#888888")
    return panel


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", "Sair"),
        ("escape", "back", "Voltar"),
    ]

    _alerts: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static(_HOME_BRAND, classes="home-brand")
            yield Static(
                f"Orquestrador de agentes de IA · v{__version__}",
                classes="home-sub",
            )
            yield Static("", id="home-alerts")
            yield OptionList(id="home-options")
            yield Static(ROOT_HINT, classes="home-hint")
            yield Input(
                placeholder=TASK_PLACEHOLDER,
                id="workflow-prompt",
                classes="-hidden",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._pending_workflow: str | None = None
        self._view = ROOT
        self._descriptions: dict[str, str] = {}
        self._default_prompts: dict[str, str] = {}
        self._alerts = []
        self._refresh_options()
        self.query_one("#workflow-prompt", Input).display = False
        self.query_one("#home-alerts", Static).display = False
        self._poll_alerts()
        self.set_interval(ALERT_POLL_SECONDS, self._poll_alerts)

    def _poll_alerts(self) -> None:
        """Ask the daemon which runs are waiting, off the event loop.

        `awaiting_runs` is HTTP with a 2s timeout. `exclusive` cancels the prior
        poll, but threads ignore cancellation, so `_fetch_alerts` checks
        `is_cancelled` and drops late results.
        """
        self.run_worker(self._fetch_alerts, exclusive=True, thread=True)

    def _fetch_alerts(self) -> None:
        runs = awaiting_runs()
        if get_current_worker().is_cancelled:
            return
        try:
            self.app.call_from_thread(self._apply_alerts, runs)
        except Exception:
            pass

    def _apply_alerts(self, runs: list[dict[str, Any]]) -> None:
        if not self.is_mounted:
            return
        changed = [str(run.get("id") or "") for run in runs] != [
            str(run.get("id") or "") for run in self._alerts
        ]
        self._alerts = runs
        panel = self.query_one("#home-alerts", Static)
        panel.display = bool(runs)
        if runs:
            panel.update(_alert_panel(runs))
        if not runs and self._view == ALERTS:
            self._view = ROOT
            self._refresh_options()
            return
        if changed and self._view in {ROOT, ALERTS}:
            self._refresh_options()

    def _update_hint(self, workflow_id: str | None = None) -> None:
        """Submenu hint: the workflow description plus the key help.

        Always two lines, even without a description, so the list does not jump.
        """
        description = self._descriptions.get(workflow_id or "", "")
        keys = (
            "Enter inicia agora"
            if self._default_prompts.get(workflow_id or "")
            else "Enter para descrever a tarefa"
        )
        self.query_one(".home-hint", Static).update(f"{description}\n{keys} · Esc volta")

    @on(OptionList.OptionHighlighted, "#home-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._view != SESSION:
            return
        option_id = str(event.option_id or "")
        self._update_hint(
            option_id.split(":", 1)[1] if option_id.startswith("workflow:") else None
        )

    def _refresh_options(self) -> None:
        options = self.query_one("#home-options", OptionList)
        options.clear_options()
        hint = self.query_one(".home-hint", Static)
        if not global_config_exists():
            self._view = ROOT
            options.add_option(Option("Configurar Pulse", id="init"))
            options.add_option(Option("Sair", id="exit"))
            hint.update(ROOT_HINT)
            return
        if self._view == ALERTS:
            for run in self._alerts:
                options.add_option(
                    Option(run_line(run, tail=held_tail(run)), id=f"attach:{run.get('id')}")
                )
            options.add_option(Option("← Voltar", id="back"))
            hint.update("Enter abre a sessão para responder · Esc volta")
            return
        if self._view == SESSION:
            workflows = _session_workflows()
            self._descriptions = {
                item.id: " → ".join(step.label for step in item.steps) for item in workflows
            }
            self._default_prompts = {
                item.id: item.default_prompt for item in workflows if item.default_prompt
            }
            for workflow in workflows:
                label = workflow.label
                if workflow.description:
                    label = f"{label} · {workflow.description}"
                options.add_option(Option(label, id=f"workflow:{workflow.id}"))
            options.add_option(Option("← Voltar", id="back"))
            self._update_hint(workflows[0].id if workflows else None)
            return
        if is_pulse_ready():
            if self._alerts:
                count = len(self._alerts)
                label = (
                    "Responder 1 sessão pendente"
                    if count == 1
                    else f"Responder {count} sessões pendentes"
                )
                options.add_option(Option(label, id="alerts"))
            options.add_option(Option("Nova sessão", id="session"))
            options.add_option(Option("Histórico", id="history"))
        else:
            options.add_option(Option("Configurar Pulse", id="init"))
        options.add_option(Option("Configurações", id="settings"))
        options.add_option(Option("Sair", id="exit"))
        hint.update(ROOT_HINT)

    @on(OptionList.OptionSelected, "#home-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        action = str(option_id)
        if action == "exit":
            self.action_quit_app()
            return
        if action == "init":
            self.app.open_onboarding()
            return
        if action == "settings":
            self.app.open_settings()
            return
        if action == "history":
            self.app.open_history()
            return
        if action == "session":
            self._view = SESSION
            self._refresh_options()
            self.query_one("#home-options", OptionList).focus()
            return
        if action == "alerts":
            self._view = ALERTS
            self._refresh_options()
            self.query_one("#home-options", OptionList).focus()
            return
        if action.startswith("attach:"):
            self._open_waiting_run(action.split(":", 1)[1])
            return
        if action == "back":
            self.action_back()
            return
        if action.startswith("workflow:"):
            workflow_id = action.split(":", 1)[1]
            default_prompt = self._default_prompts.get(workflow_id, "")
            if default_prompt:
                self.app.open_cockpit(workflow_id, default_prompt)
                return
            self._pending_workflow = workflow_id
            prompt_input = self.query_one("#workflow-prompt", Input)
            prompt_input.display = True
            prompt_input.focus()
            prompt_input.placeholder = TASK_PLACEHOLDER

    def _open_waiting_run(self, run_id: str) -> None:
        """Attach live to a waiting session; its pending prompt reopens after replay.

        Not named `_attach`: that is an internal Textual `Screen` method and
        overriding it breaks screen mounting.
        """
        run = next((item for item in self._alerts if str(item.get("id")) == run_id), None)
        if run is None:
            return
        workspace = str(run.get("workspace") or "").strip()
        self.app.open_cockpit(
            str(run.get("workflow_id") or ""),
            str(run.get("prompt") or ""),
            attach_run_id=run_id,
            workspace=Path(workspace) if workspace else None,
        )

    def action_back(self) -> None:
        """Esc: close the open prompt, otherwise go back to the root menu."""
        prompt_input = self.query_one("#workflow-prompt", Input)
        if prompt_input.display:
            prompt_input.value = ""
            prompt_input.display = False
            self._pending_workflow = None
            self.query_one("#home-options", OptionList).focus()
            return
        if self._view == ROOT:
            return
        self._view = ROOT
        self._refresh_options()
        self.query_one("#home-options", OptionList).focus()

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
        """Quit the CLI without stopping runs, which live in the engine process.

        Reports every active run, not only those awaiting input, so the user
        knows what keeps running in the background.
        """
        running = active_runs()
        if running:
            count = len(running)
            noun = "sessão continua" if count == 1 else "sessões continuam"
            self.app.exit(
                message=(
                    f"[pulse] {count} {noun} rodando em segundo plano. "
                    "Rode `pulse` e abra Histórico para acompanhar."
                )
            )
            return
        self.app.exit()

    def on_screen_resume(self) -> None:
        self._refresh_options()
        self._poll_alerts()
