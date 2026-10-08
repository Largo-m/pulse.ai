from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from pulse import vcs
from pulse.config import (
    ensure_project_workflows,
    init_project_config,
    load_project_config,
    resolve_config,
)
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.model_catalog import collect_available_models
from pulse.doctor.checks import run_environment_checks
from pulse.tui import strings

_GlobalField = Literal["runtime", "model", "permission_policy"]


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
        if vcs.is_repo(self._cwd):
            state = (
                strings.SETTINGS_WORKTREE_ON
                if self._worktree_enabled()
                else strings.SETTINGS_WORKTREE_OFF
            )
            options.append(("worktree", strings.SETTINGS_WORKTREE_OPTION.format(state=state)))
        options.append(("doctor", strings.SETTINGS_DOCTOR_OPTION))
        options.append(("back", strings.BACK))
        self._set_options(options)

    def _worktree_enabled(self) -> bool:
        project = load_project_config(self._cwd)
        return bool(project.use_worktree) if project is not None else False

    def _toggle_worktree(self) -> None:
        from pulse.config.project_config import update_project_defaults

        enabled = not self._worktree_enabled()
        update_project_defaults(self._cwd, use_worktree=enabled)
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
        if route is not None:
            route(value)

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
        runtime = self._current_fields()[0]
        models = collect_available_models(self._cwd, agent_name=runtime or None)

        def apply() -> None:
            self._mode = "pick_model"
            current = self._current_fields()[1]
            self._set_status(self._pick_title(strings.SETTINGS_PICK_MODEL))
            self._set_options([(f"model:{item}", _mark_current(item, current)) for item in models])

        self.app.call_from_thread(apply)

    def _show_permissions(self) -> None:
        self._mode = "pick_permission"
        current = self._current_fields()[2]
        self._set_status(self._pick_title(strings.SETTINGS_PICK_POLICY))
        current_label = strings.PERMISSION_LABELS.get(current, current)
        self._set_options(
            [
                (f"policy:{key}", _mark_current(strings.PERMISSION_LABELS[key], current_label))
                for key in PERMISSION_POLICIES
            ]
        )

    def _show_global_fields(self) -> None:
        """Settings that apply to every agent."""
        ensure_project_workflows(self._cwd)
        init_project_config(self._cwd)
        self._target = "global"
        self._workflow_id = None
        self._mode = "global_fields"
        runtime, model, policy = self._effective_global_fields()
        self._set_report(strings.SETTINGS_GLOBAL_REPORT)
        self._set_status(strings.SETTINGS_GLOBAL)
        self._set_options(_field_options("g", runtime, model, policy))

    def _show_pulse_agents(self) -> None:
        ensure_project_workflows(self._cwd)
        init_project_config(self._cwd)
        from pulse.store.workflow_defs import list_agents

        self._target = "agent"
        self._mode = "pick_workflow"
        self._set_report("")
        self._set_status(strings.SETTINGS_PICK_AGENT)
        options: list[tuple[str, str]] = []
        saved = self._workflow_id
        for agent in list_agents():
            self._workflow_id = agent.id
            runtime, model, _policy = self._effective_agent_fields()
            label = strings.SETTINGS_AGENT_OPTION.format(
                label=agent.label, runtime=runtime, model=model
            )
            options.append((f"workflow:{agent.id}", label))
        self._workflow_id = saved
        self._set_options(options)

    def _show_workflow_fields(self) -> None:
        self._mode = "workflow_fields"
        runtime, model, policy = self._effective_agent_fields()
        self._set_report("")
        self._set_status(self._agent_label())
        self._set_options(_field_options("wf", runtime, model, policy))

    def _project_id(self) -> str | None:
        project = load_project_config(self._cwd)
        if project is None:
            return None
        return project.project_id

    def _agent_label(self) -> str:
        from pulse.store.workflow_defs import get_agent

        agent = get_agent(self._workflow_id or "")
        return agent.label if agent is not None else (self._workflow_id or strings.AGENT)

    def _current_fields(self) -> tuple[str, str, str]:
        """Runtime, model and policy of the target being edited."""
        if self._target == "global":
            return self._effective_global_fields()
        if self._workflow_id:
            return self._effective_agent_fields()
        return "", "", ""

    def _pick_title(self, title: str) -> str:
        return (
            strings.SETTINGS_PICK_GLOBAL.format(title=title) if self._target == "global" else title
        )

    def _effective_global_fields(self) -> tuple[str, str, str]:
        """Effective values: project, else machine, else Pulse defaults."""
        from pulse.config import load_global_config

        project = load_project_config(self._cwd)
        machine = load_global_config()
        return (
            (project and project.default_agent) or (machine and machine.default_agent) or "cursor",
            (project and project.model) or (machine and machine.model) or "Auto",
            (project and project.permission_policy)
            or (machine and machine.permission_policy)
            or "ask",
        )

    def _save_global(self, *, field: _GlobalField, value: str) -> None:
        from pulse.config.project_config import update_project_defaults
        from pulse.store.agent_settings import apply_setting_to_all_agents
        from pulse.store.workflow_defs import list_agents

        if field == "runtime":
            update_project_defaults(self._cwd, agent=value)
        elif field == "model":
            update_project_defaults(self._cwd, model=value)
        else:
            update_project_defaults(self._cwd, permission_policy=value)
        project_id = self._project_id()
        if project_id:
            apply_setting_to_all_agents(
                project_id,
                field=field,
                value=value,
                agent_ids=[agent.id for agent in list_agents()],
            )
        self._show_global_fields()

    def _effective_agent_fields(self) -> tuple[str, str, str]:
        """Stored values for this agent: project settings, then its definition.

        Full resolution is avoided because it swaps an unavailable runtime for
        one the machine has, showing a value other than what the user picked.
        """
        from pulse.store.agent_settings import load_agent_settings
        from pulse.store.workflow_defs import get_agent

        agent_id = self._workflow_id or ""
        definition = get_agent(agent_id)
        runtime = definition.runtime if definition else ""
        model = definition.model if definition else ""
        policy = definition.permission_policy if definition else ""
        project_id = self._project_id()
        if project_id:
            stored = load_agent_settings(project_id, agent_id)
            runtime = str(stored.get("runtime") or runtime)
            model = str(stored.get("model") or model)
            policy = str(stored.get("permission_policy") or policy)
        fallback = self._effective_global_fields()
        return runtime or fallback[0], model or fallback[1], policy or fallback[2]

    def _show_agents(self) -> None:
        resolved = resolve_config(self._cwd, workflow=self._workflow_id)
        self._mode = "pick_agent"
        current = self._current_fields()[0]
        self._set_status(self._pick_title(strings.SETTINGS_PICK_RUNTIME))
        options = []
        for name, agent in resolved.agents.items():
            label = strings.SETTINGS_RUNTIME_OPTION.format(name=name, binary=agent.binary)
            if name == current:
                label = strings.CURRENT_MARK.format(label=label)
            options.append((f"agent:{name}", label))
        self._set_options(options)

    def _save_model(self, model: str) -> None:
        if self._target == "global":
            self._save_global(field="model", value=model)
            return
        if self._workflow_id:
            project = load_project_config(self._cwd)
            if project is None:
                from pulse.config.project_config import init_project_config

                init_project_config(self._cwd)
                project = load_project_config(self._cwd)
            if project is None:
                return
            from pulse.store.agent_settings import upsert_agent_settings

            upsert_agent_settings(project.project_id, self._workflow_id, model=model)
            self._show_workflow_fields()
            return
        self._show_root()

    def _save_permission(self, policy: str) -> None:
        if self._target == "global":
            self._save_global(field="permission_policy", value=policy)
            return
        if not self._workflow_id:
            self._show_root()
            return
        project = load_project_config(self._cwd)
        if project is None:
            return
        from pulse.store.agent_settings import upsert_agent_settings

        upsert_agent_settings(project.project_id, self._workflow_id, permission_policy=policy)
        self._show_workflow_fields()

    def _save_workflow_agent(self, agent: str) -> None:
        if self._target == "global":
            self._save_global(field="runtime", value=agent)
            return
        if not self._workflow_id:
            return
        project = load_project_config(self._cwd)
        if project is None:
            return
        from pulse.store.agent_settings import upsert_agent_settings

        upsert_agent_settings(project.project_id, self._workflow_id, runtime=agent)
        self._show_workflow_fields()

    def _run_doctor(self) -> None:
        checks = run_environment_checks()
        lines = []
        for check in checks:
            mark = "ok" if check.status == "ok" else check.status.upper()
            lines.append(f"[{mark}] {check.message}")
        from pulse.config import load_global_config

        cfg = load_global_config()
        if cfg:
            lines.append(strings.SETTINGS_DOCTOR_GLOBAL_CONFIG.format(model=cfg.model))
        project = load_project_config(self._cwd)
        if project is not None:
            lines.append(strings.SETTINGS_DOCTOR_PROJECT_CONFIG.format(source=project.source_file))
        self._mode = "doctor"
        self._set_status(strings.ENVIRONMENT)
        self._set_report("\n".join(lines) if lines else strings.SETTINGS_DOCTOR_NO_CHECKS)
        self._set_options([("back", strings.BACK)])


def _mark_current(label: str, current: str) -> str:
    if current and label == current:
        return strings.CURRENT_MARK.format(label=label)
    return label


def _field_options(prefix: str, runtime: str, model: str, policy: str) -> list[tuple[str, str]]:
    """Runtime, model and policy rows of a settings target, ids prefixed by `prefix`."""
    return [
        (f"{prefix}_agent", strings.SETTINGS_FIELD_RUNTIME.format(value=runtime)),
        (f"{prefix}_model", strings.SETTINGS_FIELD_MODEL.format(value=model)),
        (
            f"{prefix}_permission",
            strings.SETTINGS_FIELD_PERMISSIONS.format(
                value=strings.PERMISSION_LABELS.get(policy, policy)
            ),
        ),
    ]
