from __future__ import annotations

from pathlib import Path

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
from pulse.config.model_catalog import (
    PERMISSION_LABELS,
    collect_available_models,
    permission_choices,
)
from pulse.doctor.checks import run_environment_checks


class SettingsScreen(Screen[None]):
    BINDINGS = [("escape", "go_back", "Voltar"), ("q", "go_back", "Voltar"), ("b", "go_back", "Voltar")]

    def __init__(self, *, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd = (cwd or Path.cwd()).resolve()
        self._mode = "root"
        self._scope: str | None = None
        self._workflow_id: str | None = None
        self._target = "agent"

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-content"):
            yield Static("CONFIGURAÇÕES", classes="settings-title")
            yield Static("Agents e ambiente", id="settings-status", classes="settings-hint")
            yield OptionList(id="settings-options")
            yield Static("", id="settings-report", classes="settings-report")
            yield Static("Enter seleciona  ·  Esc volta", classes="settings-hint-keys")
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
        self._scope = None
        self._workflow_id = None
        self._set_report("")
        self._set_status("Agents e ambiente")
        options = [
            ("global", "Global — runtime, modelo e permissões de todos os agents"),
            ("agents", "Agents — runtime, modelo e permissões"),
        ]
        if vcs.is_repo(self._cwd):
            state = "ligado" if self._worktree_enabled() else "desligado"
            options.append(("worktree", f"Worktree — isolar cada run em branch própria · {state}"))
        options.append(("doctor", "Verificar ambiente"))
        options.append(("back", "Voltar"))
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
            "As runs deste projeto passam a rodar num `git worktree` próprio, em "
            "`~/.pulse/worktrees/`, numa branch `pulse/…` por run. A árvore de "
            "trabalho do editor fica intocada."
            if enabled
            else "As runs voltam a rodar na árvore de trabalho do projeto. "
            "Os worktrees já criados continuam onde estão."
        )

    def _show_scope(self, next_mode: str, title: str) -> None:
        self._mode = next_mode
        self._set_status(title)
        self._set_options(
            [
                ("scope:global", "Global — SQLite da máquina"),
                ("scope:project", "Projeto — SQLite por project_id"),
                ("back", "Voltar"),
            ]
        )

    @on(OptionList.OptionSelected, "#settings-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = str(event.option_id or "")
        if option_id == "back":
            self.action_go_back()
            return
        if self._mode == "root":
            if option_id == "global":
                self._show_global_fields()
            elif option_id == "agents":
                self._show_pulse_agents()
            elif option_id == "worktree":
                self._toggle_worktree()
            elif option_id == "doctor":
                self._run_doctor()
            return
        if self._mode == "global_fields":
            if option_id == "g_model":
                self._load_models()
            elif option_id == "g_agent":
                self._show_agents()
            elif option_id == "g_permission":
                self._show_permissions()
            return
        if option_id.startswith("scope:"):
            self._scope = option_id.split(":", 1)[1]
            if self._mode == "scope_model":
                self._load_models()
            elif self._mode == "scope_permissions":
                self._show_permissions()
            elif self._mode == "scope_workflows":
                self._show_workflows()
            return
        if self._mode == "pick_model" and option_id.startswith("model:"):
            self._save_model(option_id.split(":", 1)[1])
            return
        if self._mode == "pick_permission" and option_id.startswith("policy:"):
            self._save_permission(option_id.split(":", 1)[1])
            return
        if self._mode == "pick_workflow" and option_id.startswith("workflow:"):
            self._workflow_id = option_id.split(":", 1)[1]
            self._show_workflow_fields()
            return
        if self._mode == "workflow_fields":
            if option_id == "wf_model":
                self._load_models(for_workflow=True)
            elif option_id == "wf_agent":
                self._show_agents()
            elif option_id == "wf_permission":
                self._show_permissions()
            return
        if self._mode == "pick_agent" and option_id.startswith("agent:"):
            self._save_workflow_agent(option_id.split(":", 1)[1])

    @work(thread=True)
    def _load_models(self, *, for_workflow: bool = False) -> None:
        self.app.call_from_thread(self._set_status, "Carregando modelos…")
        runtime = self._current_fields()[0]
        models = collect_available_models(self._cwd, agent_name=runtime or None)

        def apply() -> None:
            self._mode = "pick_model"
            current = self._current_fields()[1]
            self._set_status(self._pick_title("Escolha o modelo"))
            self._set_options(
                [(f"model:{item}", _mark_current(item, current)) for item in models]
            )

        self.app.call_from_thread(apply)

    def _show_permissions(self) -> None:
        self._mode = "pick_permission"
        current = self._current_fields()[2]
        self._set_status(self._pick_title("Escolha a política de permissões"))
        self._set_options(
            [
                (f"policy:{key}", _mark_current(label, PERMISSION_LABELS.get(current, current)))
                for key, label in permission_choices()
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
        self._set_report(
            "O global sobrescreve todos os agents. Trocar um agent depois vale só para ele."
        )
        self._set_status("Global")
        self._set_options(
            [
                ("g_agent", f"Runtime — {runtime}"),
                ("g_model", f"Modelo — {model}"),
                ("g_permission", f"Permissões — {PERMISSION_LABELS.get(policy, policy)}"),
            ]
        )

    def _show_pulse_agents(self) -> None:
        ensure_project_workflows(self._cwd)
        init_project_config(self._cwd)
        from pulse.store.workflow_defs import list_agents

        self._target = "agent"
        self._mode = "pick_workflow"
        self._set_report("")
        self._set_status("Escolha o agent")
        options: list[tuple[str, str]] = []
        saved = self._workflow_id
        for agent in list_agents():
            self._workflow_id = agent.id
            runtime, model, _policy = self._effective_agent_fields()
            options.append((f"workflow:{agent.id}", f"{agent.label} — {runtime} · {model}"))
        self._workflow_id = saved
        self._set_options(options)

    def _show_workflow_fields(self) -> None:
        self._mode = "workflow_fields"
        runtime, model, policy = self._effective_agent_fields()
        policy_label = PERMISSION_LABELS.get(policy, policy)
        self._set_report("")
        self._set_status(self._agent_label())
        self._set_options(
            [
                ("wf_agent", f"Runtime — {runtime}"),
                ("wf_model", f"Modelo — {model}"),
                ("wf_permission", f"Permissões — {policy_label}"),
            ]
        )

    def _project_id(self) -> str | None:
        project = load_project_config(self._cwd)
        if project is None:
            return None
        return project.project_id

    def _agent_label(self) -> str:
        from pulse.store.workflow_defs import get_agent

        agent = get_agent(self._workflow_id or "")
        return agent.label if agent is not None else (self._workflow_id or "Agent")

    def _current_fields(self) -> tuple[str, str, str]:
        """Runtime, model and policy of the target being edited."""
        if self._target == "global":
            return self._effective_global_fields()
        if self._workflow_id:
            return self._effective_agent_fields()
        return "", "", ""

    def _pick_title(self, title: str) -> str:
        return f"{title} (global)" if self._target == "global" else title

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

    def _save_global(self, *, field: str, value: str) -> None:
        from pulse.config.project_config import update_project_defaults
        from pulse.store.workflow_defs import list_agents
        from pulse.store.agent_settings import apply_setting_to_all_agents

        kwargs = {
            "runtime": {"agent": value},
            "model": {"model": value},
            "permission_policy": {"permission_policy": value},
        }[field]
        update_project_defaults(self._cwd, **kwargs)
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
        self._set_status(self._pick_title("Escolha o runtime"))
        options = []
        for name, agent in resolved.agents.items():
            label = f"{name} — {agent.binary}"
            if name == current:
                label = f"{label}  · atual"
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
            lines.append(f"[ok] Config global · modelo={cfg.model}")
        project = load_project_config(self._cwd)
        if project is not None:
            lines.append(f"[ok] Config projeto · {project.source_file}")
        self._mode = "doctor"
        self._set_status("Ambiente")
        self._set_report("\n".join(lines) if lines else "Nenhum check")
        self._set_options([("back", "Voltar")])


def _mark_current(label: str, current: str) -> str:
    if current and label == current:
        return f"{label}  · atual"
    return label
