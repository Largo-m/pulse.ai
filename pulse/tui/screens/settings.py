from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from pulse.tui import engine, strings
from pulse.tui.engine import AgentField, EngineUnavailable, Fields, ProjectSettings


class SettingsScreen(Screen[None]):
    BINDINGS = [
        ("escape", "go_back", strings.BACK),
        ("q", "go_back", strings.BACK),
        ("b", "go_back", strings.BACK),
    ]

    def __init__(self, *, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd = (cwd or Path.cwd()).resolve()
        self._mode = "root"
        self._workflow_id: str | None = None
        self._target = "agent"
        self._settings: ProjectSettings | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-content"):
            yield Static(strings.SETTINGS_TITLE, classes="settings-title")
            yield Static(
                strings.SETTINGS_ROOT_STATUS, id="settings-status", classes="settings-hint"
            )
            yield OptionList(id="settings-options")
            yield Static("", id="settings-report", classes="settings-report")
            yield Static(strings.SETTINGS_HINT_KEYS, classes="settings-hint-keys")
        yield Footer()

    def on_mount(self) -> None:
        self._set_report("")
        self._show_root()

    def action_go_back(self) -> None:
        if self._mode == "root":
            self.app.pop_screen()
            return
        if self._mode in {"pick_model", "pick_permission", "pick_agent"}:
            if self._target == "global":
                self._show_global_fields()
                return
            if self._workflow_id:
                self._show_workflow_fields()
                return
        if self._mode in {"workflow_fields", "doctor"}:
            self._show_pulse_agents() if self._mode == "workflow_fields" else self._show_root()
            return
        self._show_root()

    def _set_status(self, text: str) -> None:
        self.query_one("#settings-status", Static).update(text)

    def _set_report(self, text: str) -> None:
        widget = self.query_one("#settings-report", Static)
        widget.update(text)
        widget.display = bool(text)

    def _set_options(self, options: list[tuple[str, str]]) -> None:
        widget = self.query_one("#settings-options", OptionList)
        widget.clear_options()
        widget.display = True
        for option_id, label in options:
            widget.add_option(Option(label, id=option_id))
        if options:
            widget.focus()

    def _show_root(self) -> None:
        self._mode = "root"
        self._workflow_id = None
        self._set_report("")
        self._set_status(strings.SETTINGS_ROOT_STATUS)
        options = [
            ("global", strings.SETTINGS_GLOBAL_OPTION),
            ("agents", strings.SETTINGS_AGENTS_OPTION),
        ]
        try:
            settings = self._load()
        except EngineUnavailable as error:
            self._set_report(strings.ENGINE_UNAVAILABLE.format(error=error))
            self._set_options([("back", strings.BACK)])
            return
        if settings.is_repo:
            state = (
                strings.SETTINGS_WORKTREE_ON
                if settings.use_worktree
                else strings.SETTINGS_WORKTREE_OFF
            )
            options.append(("worktree", strings.SETTINGS_WORKTREE_OPTION.format(state=state)))
        options.append(("doctor", strings.SETTINGS_DOCTOR_OPTION))
        options.append(("back", strings.BACK))
        self._set_options(options)

    def _load(self) -> ProjectSettings:
        """The project's settings as the daemon resolves them; reread after every write."""
        self._settings = engine.project_settings(self._cwd)
        return self._settings

    def _current(self) -> ProjectSettings:
        return self._settings if self._settings is not None else self._load()

    def _toggle_worktree(self) -> None:
        enabled = not self._current().use_worktree
        engine.set_worktree(self._cwd, enabled=enabled)
        self._show_root()
        self._set_report(
            strings.SETTINGS_WORKTREE_ENABLED if enabled else strings.SETTINGS_WORKTREE_DISABLED
        )

    @on(OptionList.OptionSelected, "#settings-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = str(event.option_id or "")
        if option_id == "back":
            self.action_go_back()
            return
        action, separator, value = option_id.partition(":")
        route = self._option_routes().get((self._mode, action + separator))
        if route is None:
            return
        try:
            route(value)
        except EngineUnavailable as error:
            self._set_report(strings.ENGINE_UNAVAILABLE.format(error=error))

    def _option_routes(self) -> dict[tuple[str, str], Callable[[str], object]]:
        """What each option does, keyed by the menu showing it and its id.

        Pick options carry their value after the `:` (`model:<name>`); the
        route receives that value, the other routes ignore it.
        """
        open_fields: dict[str, Callable[[str], object]] = {
            "agent": lambda _: self._show_agents(),
            "model": lambda _: self._load_models(),
            "permission": lambda _: self._show_permissions(),
        }
        return {
            ("root", "global"): lambda _: self._show_global_fields(),
            ("root", "agents"): lambda _: self._show_pulse_agents(),
            ("root", "worktree"): lambda _: self._toggle_worktree(),
            ("root", "doctor"): lambda _: self._run_doctor(),
            **{("global_fields", f"g_{field}"): route for field, route in open_fields.items()},
            **{("workflow_fields", f"wf_{field}"): route for field, route in open_fields.items()},
            ("pick_model", "model:"): self._save_model,
            ("pick_permission", "policy:"): self._save_permission,
            ("pick_workflow", "workflow:"): self._show_agent_fields,
            ("pick_agent", "agent:"): self._save_workflow_agent,
        }

    def _show_agent_fields(self, agent_id: str) -> None:
        self._workflow_id = agent_id
        self._show_workflow_fields()

    @work(thread=True)
    def _load_models(self) -> None:
        self.app.call_from_thread(self._set_status, strings.SETTINGS_LOADING_MODELS)
        runtime = self._current_fields().runtime
        try:
            models = engine.models(self._cwd, runtime)
        except EngineUnavailable as error:
            self.app.call_from_thread(
                self._set_report, strings.ENGINE_UNAVAILABLE.format(error=error)
            )
            return

        def apply() -> None:
            self._mode = "pick_model"
            current = self._current_fields().model
            self._set_status(self._pick_title(strings.SETTINGS_PICK_MODEL))
            self._set_options([(f"model:{item}", _mark_current(item, current)) for item in models])

        self.app.call_from_thread(apply)

    def _show_permissions(self) -> None:
        self._mode = "pick_permission"
        current = self._current_fields().permission_policy
        self._set_status(self._pick_title(strings.SETTINGS_PICK_POLICY))
        current_label = strings.PERMISSION_LABELS.get(current, current)
        self._set_options(
            [
                (
                    f"policy:{key}",
                    _mark_current(strings.PERMISSION_LABELS.get(key, key), current_label),
                )
                for key in self._current().permission_policies
            ]
        )

    def _show_global_fields(self) -> None:
        """Settings that apply to every agent."""
        engine.open_project(self._cwd)
        self._target = "global"
        self._workflow_id = None
        self._mode = "global_fields"
        defaults = self._load().defaults
        self._set_report(strings.SETTINGS_GLOBAL_REPORT)
        self._set_status(strings.SETTINGS_GLOBAL)
        self._set_options(_field_options("g", defaults))

    def _show_pulse_agents(self) -> None:
        engine.open_project(self._cwd)
        self._target = "agent"
        self._mode = "pick_workflow"
        self._set_report("")
        self._set_status(strings.SETTINGS_PICK_AGENT)
        self._set_options(
            [
                (
                    f"workflow:{agent.id}",
                    strings.SETTINGS_AGENT_OPTION.format(
                        label=agent.label, runtime=agent.fields.runtime, model=agent.fields.model
                    ),
                )
                for agent in self._load().agents
            ]
        )

    def _show_workflow_fields(self) -> None:
        self._mode = "workflow_fields"
        self._load()
        self._set_report("")
        self._set_status(self._agent_label())
        self._set_options(_field_options("wf", self._current_fields()))

    def _agent_label(self) -> str:
        agent = self._current().agent(self._workflow_id or "")
        return agent.label if agent is not None else (self._workflow_id or strings.AGENT)

    def _current_fields(self) -> Fields:
        """Runtime, model and policy of the target being edited."""
        settings = self._current()
        if self._target == "global":
            return settings.defaults
        agent = settings.agent(self._workflow_id or "")
        return agent.fields if agent is not None else Fields("", "", "")

    def _pick_title(self, title: str) -> str:
        return (
            strings.SETTINGS_PICK_GLOBAL.format(title=title) if self._target == "global" else title
        )

    def _save(self, field: AgentField, value: str) -> None:
        """Write the picked value for the target being edited, then show its fields again."""
        if self._target == "global":
            engine.save_default(self._cwd, field, value)
            self._show_global_fields()
            return
        if not self._workflow_id:
            self._show_root()
            return
        engine.save_agent_field(self._cwd, self._workflow_id, field, value)
        self._show_workflow_fields()

    def _show_agents(self) -> None:
        self._mode = "pick_agent"
        current = self._current_fields().runtime
        self._set_status(self._pick_title(strings.SETTINGS_PICK_RUNTIME))
        options = []
        for name, binary in self._current().runtimes:
            label = strings.SETTINGS_RUNTIME_OPTION.format(name=name, binary=binary)
            if name == current:
                label = strings.CURRENT_MARK.format(label=label)
            options.append((f"agent:{name}", label))
        self._set_options(options)

    def _save_model(self, model: str) -> None:
        self._save("model", model)

    def _save_permission(self, policy: str) -> None:
        self._save("permission_policy", policy)

    def _save_workflow_agent(self, runtime: str) -> None:
        self._save("runtime", runtime)

    def _run_doctor(self) -> None:
        lines = [
            f"[{'ok' if check.status == 'ok' else check.status.upper()}] {check.message}"
            for check in engine.doctor_checks()
        ]
        config = engine.config(self._cwd)
        machine = config.get("global")
        if machine:
            lines.append(strings.SETTINGS_DOCTOR_GLOBAL_CONFIG.format(model=machine.get("model")))
        project = config.get("project")
        if project:
            lines.append(
                strings.SETTINGS_DOCTOR_PROJECT_CONFIG.format(source=project.get("source_file"))
            )
        self._mode = "doctor"
        self._set_status(strings.ENVIRONMENT)
        self._set_report("\n".join(lines) if lines else strings.SETTINGS_DOCTOR_NO_CHECKS)
        self._set_options([("back", strings.BACK)])


def _mark_current(label: str, current: str) -> str:
    if current and label == current:
        return strings.CURRENT_MARK.format(label=label)
    return label


def _field_options(prefix: str, fields: Fields) -> list[tuple[str, str]]:
    """Runtime, model and policy rows of a settings target, ids prefixed by `prefix`."""
    policy = fields.permission_policy
    return [
        (f"{prefix}_agent", strings.SETTINGS_FIELD_RUNTIME.format(value=fields.runtime)),
        (f"{prefix}_model", strings.SETTINGS_FIELD_MODEL.format(value=fields.model)),
        (
            f"{prefix}_permission",
            strings.SETTINGS_FIELD_PERMISSIONS.format(
                value=strings.PERMISSION_LABELS.get(policy, policy)
            ),
        ),
    ]
