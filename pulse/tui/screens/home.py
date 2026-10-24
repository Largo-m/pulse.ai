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
from textual.widgets import Footer, OptionList, Static
from textual.worker import get_current_worker

from pulse import __version__
from pulse.client.active_runs import active_runs, awaiting_runs
from pulse.client.protocol import RunForm
from pulse.domain.branch_name import task_slug
from pulse.domain.git_options import NO_GIT_OPTIONS, GitOptions
from pulse.history.run_lines import held_tail, run_line
from pulse.history.status_labels import status_color, status_icon
from pulse.tui import engine, strings
from pulse.tui.brand import BANNER, PULSE_LINE, PULSE_WAVE
from pulse.tui.key_hints import key_line
from pulse.tui.menu_rows import MenuRow, breadcrumb
from pulse.tui.palette import TEXT, TEXT_MUTED
from pulse.tui.screens.branch_name import BranchNameScreen, branch_problem
from pulse.tui.screens.navigation import pulse_app
from pulse.tui.widgets.menu_list import MenuList
from pulse.tui.widgets.task_form import TaskDraft, TaskForm


def _home_brand() -> str:
    logo_lines = BANNER.strip("\n").splitlines()
    wave_lines = (PULSE_LINE, PULSE_WAVE)
    width = max(len(line) for line in (*logo_lines, *wave_lines))
    parts = [line.ljust(width) for line in (*logo_lines, *wave_lines)]
    return "\n".join(parts)


_HOME_BRAND = _home_brand()


def _session_workflows() -> list[engine.WorkflowShape]:
    """Workflows offered by the new-session menu: the pipelines, sorted by label.

    The generic loop (`is_default`) is hidden from this menu only; it remains
    available in the database and the daemon API. A daemon that stopped
    answering leaves the menu empty rather than closing the app.
    """
    try:
        listed = engine.workflows()
    except engine.EngineError:
        return []
    return sorted((item for item in listed if not item.is_default), key=lambda item: item.label)


def _run_form(draft: TaskDraft) -> RunForm:
    git = draft.git or NO_GIT_OPTIONS
    return RunForm(
        title=draft.brief.title,
        description=draft.brief.description,
        use_worktree=git.use_worktree,
        atomic_commits=git.atomic_commits,
        auto_pull_request=git.auto_pull_request,
    )


def _step_chain(workflow: engine.WorkflowShape) -> str:
    return " → ".join(label for _step_id, label in workflow.steps)


def _workflow_row(workflow: engine.WorkflowShape) -> MenuRow:
    """A workflow in the new-session picker: its size and whether it asks for a task."""
    count = len(workflow.steps)
    value = (
        strings.HOME_SESSION_STEP_ONE
        if count == 1
        else strings.HOME_SESSION_STEPS.format(count=count)
    )
    if workflow.default_prompt:
        value = f"{value} · {strings.HOME_SESSION_STARTS_NOW}"
    return MenuRow(f"workflow:{workflow.id}", workflow.label, value, workflow.description)


def _setup() -> engine.SetupState | engine.EngineError:
    """Where the first run stands, or why the daemon could not say."""
    try:
        return engine.setup_state(Path.cwd())
    except engine.EngineError as error:
        return error


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
            yield Static("", id="home-header")
            yield Static("", id="home-alerts")
            yield MenuList(id="home-options")
            yield Static(strings.HOME_ROOT_HINT, classes="home-hint")
            yield TaskForm(id="task-form")
        yield Static(key_line(strings.HOME_SESSION_KEYS), id="home-keys")
        yield Footer()

    def on_mount(self) -> None:
        self._pending_workflow: str | None = None
        self._view = ROOT
        self._workflows: dict[str, engine.WorkflowShape] = {}
        self._alerts = []
        self._refresh_options()
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
        """The pointed workflow's step chain and what Enter will do with it."""
        hint = self.query_one(".home-hint", Static)
        workflow = self._workflows.get(workflow_id or "")
        if workflow is None:
            hint.update(Text(strings.HOME_SESSION_EMPTY, style=TEXT_MUTED))
            return
        action = strings.HOME_START_NOW if workflow.default_prompt else strings.HOME_DESCRIBE_TASK
        detail = Text(_step_chain(workflow), style=TEXT)
        detail.append(f"\n{action}", style=TEXT_MUTED)
        hint.update(detail)

    @on(OptionList.OptionHighlighted, "#home-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._view != SESSION:
            return
        option_id = str(event.option_id or "")
        self._update_hint(option_id.split(":", 1)[1] if option_id.startswith("workflow:") else None)

    def _refresh_options(self, *, focus: str | None = None) -> None:
        options = self.query_one("#home-options", MenuList)
        hint = self.query_one(".home-hint", Static)
        setup = _setup()
        if isinstance(setup, engine.EngineError):
            self._offer_setup(options, hint, setup)
            return
        if not setup.configured:
            self._offer_setup(options, hint, None)
            return
        self.set_class(self._view == SESSION, "-picker")
        if self._view == ALERTS:
            rows = [
                MenuRow(f"attach:{run.get('id')}", run_line(run, tail=held_tail(run)))
                for run in self._alerts
            ]
            options.show_rows([*rows, MenuRow("back", strings.BACK_ARROW)])
            hint.update(strings.HOME_ALERTS_HINT)
            return
        if self._view == SESSION:
            self._show_session(options)
            return
        rows = []
        if setup.ready:
            if self._alerts:
                count = len(self._alerts)
                label = (
                    strings.HOME_ANSWER_ONE
                    if count == 1
                    else strings.HOME_ANSWER_MANY.format(count=count)
                )
                rows.append(MenuRow("alerts", label))
            rows.append(MenuRow("session", strings.HOME_NEW_SESSION))
            rows.append(MenuRow("history", strings.HOME_HISTORY))
        else:
            rows.append(MenuRow("init", strings.HOME_SETUP))
        rows.append(MenuRow("settings", strings.HOME_SETTINGS))
        rows.append(MenuRow("exit", strings.QUIT))
        options.show_rows(rows, focus=focus)
        hint.update(strings.HOME_ROOT_HINT)

    def _show_session(self, options: MenuList) -> None:
        """The workflow picker, laid out like an agent CLI's: no banner, one row per workflow."""
        workflows = _session_workflows()
        self._workflows = {item.id: item for item in workflows}
        header = breadcrumb(strings.HOME_NEW_SESSION, (), Path.cwd().name)
        header.append(f"\n{strings.HOME_SESSION_PROMPT}", style=TEXT_MUTED)
        self.query_one("#home-header", Static).update(header)
        options.show_rows([_workflow_row(workflow) for workflow in workflows])
        pointed = options.pointed
        self._update_hint(pointed.id.partition(":")[2] if pointed else None)

    def _offer_setup(
        self, options: MenuList, hint: Static, failure: engine.EngineError | None
    ) -> None:
        self._view = ROOT
        self.set_class(False, "-picker")
        rows = []
        # Screens never start the daemon themselves, so Home is where it comes back.
        if isinstance(failure, engine.EngineUnavailable):
            rows.append(MenuRow("start_engine", strings.HOME_START_ENGINE))
        rows.append(MenuRow("init", strings.HOME_SETUP))
        rows.append(MenuRow("exit", strings.QUIT))
        options.show_rows(rows)
        hint.update(failure.describe() if failure is not None else strings.HOME_ROOT_HINT)

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
            "start_engine": lambda _: self._start_engine(),
            "settings": lambda _: pulse_app(self).open_settings(),
            "history": lambda _: pulse_app(self).open_history(),
            "session": lambda _: self._show_view(SESSION),
            "alerts": lambda _: self._show_view(ALERTS),
            "attach": self._open_waiting_run,
            "back": lambda _: self.action_back(),
            "workflow": self._choose_workflow,
        }

    def _start_engine(self) -> None:
        self.query_one(".home-hint", Static).update(strings.HOME_ENGINE_STARTING)
        # Its own group: the alert poll is `exclusive` too and would cancel it.
        self.run_worker(self._bring_engine_up, group="engine", exclusive=True, thread=True)

    def _bring_engine_up(self) -> None:
        try:
            engine.start_daemon()
        except engine.EngineError as error:
            failure: engine.EngineError | None = error
        else:
            failure = None
        # The app already exited while the daemon was starting.
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(self._engine_started, failure)

    def _engine_started(self, failure: engine.EngineError | None) -> None:
        if not self.is_mounted:
            return
        self._refresh_options()
        if failure is not None:
            self.query_one(".home-hint", Static).update(failure.describe())

    def _show_view(self, view: str) -> None:
        """Switch menus; going back up points at the row that led down (`session`, `alerts`)."""
        came_from = self._view
        self._view = view
        self._refresh_options(focus=came_from)
        self.query_one("#home-options", OptionList).focus()

    def _choose_workflow(self, workflow_id: str) -> None:
        """Start right away when the workflow has a default prompt; otherwise ask for one."""
        workflow = self._workflows.get(workflow_id)
        if workflow is None:
            return
        if workflow.default_prompt:
            self._open_run(workflow_id, workflow.default_prompt)
            return
        self._open_form(workflow)

    def _open_form(self, workflow: engine.WorkflowShape) -> None:
        """Swap the menu for the run form, its git options seeded from the project's.

        Menu and banner leave the screen so the form fits a 24-row terminal.
        """
        try:
            settings = engine.project_settings(Path.cwd())
        except engine.EngineError as error:
            self.query_one(".home-hint", Static).update(error.describe())
            return
        self._pending_workflow = workflow.id
        git = (
            GitOptions.chained(
                use_worktree=settings.use_worktree,
                atomic_commits=settings.atomic_commits,
                auto_pull_request=settings.auto_pull_request,
            )
            if settings.is_repo
            else None
        )
        self._set_composing(True)
        self.query_one("#task-form", TaskForm).open(
            heading=breadcrumb(strings.HOME_NEW_SESSION, (workflow.label,), Path.cwd().name),
            summary=workflow.description or _step_chain(workflow),
            git=git,
        )
        self.run_worker(self._fetch_files, group="files", exclusive=True, thread=True)

    def _fetch_files(self) -> None:
        """Without the list the form still works: `@` is then plain text."""
        try:
            files = engine.workspace_files(Path.cwd())
        except engine.EngineError:
            return
        if get_current_worker().is_cancelled:
            return
        # The app already exited while the request was in flight.
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(self._offer_files, files)

    def _offer_files(self, files: list[str]) -> None:
        if self.is_mounted and self._pending_workflow is not None:
            self.query_one("#task-form", TaskForm).offer_files(files)

    def _close_form(self) -> None:
        self._pending_workflow = None
        self._set_composing(False)
        self.query_one("#home-options", OptionList).focus()

    def _set_composing(self, composing: bool) -> None:
        """The form takes the menu's place; `home_theme.py` swaps what is shown."""
        self.set_class(composing, "-composing")

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
        """Esc: close the run form, otherwise go back to the root menu."""
        if self.has_class("-composing"):
            self._close_form()
            return
        if self._view != ROOT:
            self._show_view(ROOT)

    @on(TaskForm.Submitted, "#task-form")
    def on_task_submitted(self, event: TaskForm.Submitted) -> None:
        """Start the run from the form.

        A plain description runs as it always did, on the project's git options
        and its branch confirmation. A detailed draft carries its own; a branch
        that cannot be created keeps the form open on the slug.
        """
        workflow_id = self._pending_workflow
        if not workflow_id:
            return
        draft = event.draft
        if not draft.detailed:
            self._close_form()
            self._open_run(workflow_id, draft.brief.prompt)
            return
        branch = ""
        if draft.git is not None and draft.git.use_worktree:
            branch = draft.slug
            problem = branch_problem(Path.cwd(), branch)
            if problem:
                event.form.show_error(problem)
                return
        self._close_form()
        pulse_app(self).open_cockpit(
            workflow_id, draft.brief.prompt, branch=branch, form=_run_form(draft)
        )

    def _open_run(self, workflow_id: str, text: str) -> None:
        """Start a workflow that brings its own task, confirming the branch when needed."""
        workspace = Path.cwd()
        try:
            settings = engine.project_settings(workspace)
        except engine.EngineError as error:
            self.query_one(".home-hint", Static).update(error.describe())
            return
        if not settings.use_worktree:
            pulse_app(self).open_cockpit(workflow_id, text)
            return

        def _chosen(name: str | None) -> None:
            if name:
                pulse_app(self).open_cockpit(workflow_id, text, branch=name)

        self.app.push_screen(
            BranchNameScreen(suggested=task_slug(text), workspace=workspace),
            _chosen,
        )

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
