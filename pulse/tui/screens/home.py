from __future__ import annotations

import contextlib
from collections.abc import Callable
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
from pulse.client.active_runs import active_runs, awaiting_runs, held_tail, run_line
from pulse.config import global_config_exists
from pulse.config.ready import is_pulse_ready
from pulse.history.status_labels import status_color, status_icon
from pulse.store.workflow_defs import list_workflows
from pulse.tui import strings
from pulse.tui.brand import BANNER, PULSE_LINE, PULSE_WAVE
from pulse.tui.screens.navigation import pulse_app


def _home_brand() -> str:
    logo_lines = BANNER.strip("\n").splitlines()
    wave_lines = (PULSE_LINE, PULSE_WAVE)
    width = max(len(line) for line in (*logo_lines, *wave_lines))
    parts = [line.ljust(width) for line in (*logo_lines, *wave_lines)]
    return "\n".join(parts)


_HOME_BRAND = _home_brand()


def _session_workflows() -> list:
    """Workflows offered by the new-session menu: the pipelines, sorted by label.

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


def _alert_panel(runs: list[dict[str, Any]]) -> Text:
    """Alert panel listing how many sessions are waiting and which ones.

    One line per session, not just a count, so the user can tell which run needs them.
    """
    tone = status_color("awaiting_input")
    count = len(runs)
    header = strings.HOME_ALERTS_ONE if count == 1 else strings.HOME_ALERTS_MANY
    panel = Text()
    panel.append(f"{status_icon('awaiting_input')} {header.format(count=count)}", style=tone)
    for run in runs:
        panel.append(f"\n   {run_line(run, tail=held_tail(run))}", style="#888888")
    return panel


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", strings.QUIT),
        ("escape", "back", strings.BACK),
    ]

    _alerts: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static(_HOME_BRAND, classes="home-brand")
            yield Static(
                strings.HOME_SUBTITLE.format(version=__version__),
                classes="home-sub",
            )
            yield Static("", id="home-alerts")
            yield OptionList(id="home-options")
            yield Static(strings.HOME_ROOT_HINT, classes="home-hint")
            yield Input(
                placeholder=strings.HOME_TASK_PLACEHOLDER,
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
        # The app already exited while the poll was in flight.
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(self._apply_alerts, runs)

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
            strings.HOME_START_NOW
            if self._default_prompts.get(workflow_id or "")
            else strings.HOME_DESCRIBE_TASK
        )
        self.query_one(".home-hint", Static).update(
            strings.HOME_SESSION_HINT.format(description=description, keys=keys)
        )

    @on(OptionList.OptionHighlighted, "#home-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._view != SESSION:
            return
        option_id = str(event.option_id or "")
        self._update_hint(option_id.split(":", 1)[1] if option_id.startswith("workflow:") else None)

    def _refresh_options(self) -> None:
        options = self.query_one("#home-options", OptionList)
        options.clear_options()
        hint = self.query_one(".home-hint", Static)
        if not global_config_exists():
            self._view = ROOT
            options.add_option(Option(strings.HOME_SETUP, id="init"))
            options.add_option(Option(strings.QUIT, id="exit"))
            hint.update(strings.HOME_ROOT_HINT)
            return
        if self._view == ALERTS:
            for run in self._alerts:
                options.add_option(
                    Option(run_line(run, tail=held_tail(run)), id=f"attach:{run.get('id')}")
                )
            options.add_option(Option(strings.BACK_ARROW, id="back"))
            hint.update(strings.HOME_ALERTS_HINT)
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
            options.add_option(Option(strings.BACK_ARROW, id="back"))
            self._update_hint(workflows[0].id if workflows else None)
            return
        if is_pulse_ready():
            if self._alerts:
                count = len(self._alerts)
                label = (
                    strings.HOME_ANSWER_ONE
                    if count == 1
                    else strings.HOME_ANSWER_MANY.format(count=count)
                )
                options.add_option(Option(label, id="alerts"))
            options.add_option(Option(strings.HOME_NEW_SESSION, id="session"))
            options.add_option(Option(strings.HOME_HISTORY, id="history"))
        else:
            options.add_option(Option(strings.HOME_SETUP, id="init"))
        options.add_option(Option(strings.HOME_SETTINGS, id="settings"))
        options.add_option(Option(strings.QUIT, id="exit"))
        hint.update(strings.HOME_ROOT_HINT)

    @on(OptionList.OptionSelected, "#home-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        action, _, argument = str(event.option_id).partition(":")
        route = self._option_routes().get(action)
        if route is not None:
            route(argument)

    def _option_routes(self) -> dict[str, Callable[[str], None]]:
        """What each menu option does; `attach:` and `workflow:` carry an id."""
        return {
            "exit": lambda _: self.action_quit_app(),
            "init": lambda _: pulse_app(self).open_onboarding(),
            "settings": lambda _: pulse_app(self).open_settings(),
            "history": lambda _: pulse_app(self).open_history(),
            "session": lambda _: self._show_view(SESSION),
            "alerts": lambda _: self._show_view(ALERTS),
            "attach": self._open_waiting_run,
            "back": lambda _: self.action_back(),
            "workflow": self._choose_workflow,
        }

    def _show_view(self, view: str) -> None:
        self._view = view
        self._refresh_options()
        self.query_one("#home-options", OptionList).focus()

    def _choose_workflow(self, workflow_id: str) -> None:
        """Start right away when the workflow has a default prompt; otherwise ask for one."""
        default_prompt = self._default_prompts.get(workflow_id, "")
        if default_prompt:
            pulse_app(self).open_cockpit(workflow_id, default_prompt)
            return
        self._pending_workflow = workflow_id
        prompt_input = self.query_one("#workflow-prompt", Input)
        prompt_input.display = True
        prompt_input.focus()
        prompt_input.placeholder = strings.HOME_TASK_PLACEHOLDER

    def _open_waiting_run(self, run_id: str) -> None:
        """Attach live to a waiting session; its pending prompt reopens after replay.

        Not named `_attach`: that is an internal Textual `Screen` method and
        overriding it breaks screen mounting.
        """
        run = next((item for item in self._alerts if str(item.get("id")) == run_id), None)
        if run is None:
            return
        workspace = str(run.get("workspace") or "").strip()
        pulse_app(self).open_cockpit(
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
        if self._view != ROOT:
            self._show_view(ROOT)

    @on(Input.Submitted, "#workflow-prompt")
    def on_prompt_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        workflow_id = self._pending_workflow
        event.input.value = ""
        event.input.display = False
        self._pending_workflow = None
        if not workflow_id or not text:
            return
        pulse_app(self).open_cockpit(workflow_id, text)

    def action_quit_app(self) -> None:
        """Quit the CLI without stopping runs, which live in the engine process.

        Reports every active run, not only those awaiting input, so the user
        knows what keeps running in the background.
        """
        running = active_runs()
        if running:
            count = len(running)
            message = (
                strings.HOME_EXIT_RUNNING_ONE if count == 1 else strings.HOME_EXIT_RUNNING_MANY
            )
            self.app.exit(message=message.format(count=count))
            return
        self.app.exit()

    def on_screen_resume(self) -> None:
        self._refresh_options()
        self._poll_alerts()
