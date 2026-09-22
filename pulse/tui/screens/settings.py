from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from pulse.config import (
    ensure_project_workflows,
    global_config_exists,
    load_global_config,
    load_project_config,
    resolve_config,
    update_global_defaults,
    update_global_workflow,
    update_project_defaults,
    update_project_workflow,
)
from pulse.config.model_catalog import (
    PERMISSION_LABELS,
    collect_available_models,
    permission_choices,
)
from pulse.doctor.checks import run_environment_checks
from pulse.plan.spec_types import SPEC_TYPES


class SettingsScreen(Screen[None]):
    BINDINGS = [("escape", "go_back", "Voltar"), ("q", "go_back", "Voltar")]

    def __init__(self, *, cwd: Path | None = None) -> None:
        super().__init__()
        self._cwd = (cwd or Path.cwd()).resolve()
        self._mode = "root"
        self._scope: str | None = None
        self._workflow_id: str | None = None
        self._status = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-content"):
            yield Static("Configurações", classes="home-brand")
            yield Static("", id="settings-status", classes="home-sub")
            yield OptionList(id="settings-options")
            yield Static("Enter seleciona · Esc volta", classes="home-hint")
        yield Footer()

    def on_mount(self) -> None:
        self._show_root()

    def action_go_back(self) -> None:
        if self._mode == "root":
            self.app.pop_screen()
            return
        self._show_root()

    def _set_status(self, text: str) -> None:
        self._status = text
        self.query_one("#settings-status", Static).update(text)

    def _set_options(self, options: list[tuple[str, str]]) -> None:
        widget = self.query_one("#settings-options", OptionList)
        widget.clear_options()
        for option_id, label in options:
            widget.add_option(Option(label, id=option_id))
        widget.focus()

    def _show_root(self) -> None:
        self._mode = "root"
        self._scope = None
        self._workflow_id = None
        self._set_status(self._status or "Escolha o que configurar")
        self._set_options(
            [
                ("model", "Modelo"),
                ("permissions", "Permissões"),
                ("workflows", "Workflows"),
                ("doctor", "Verificar ambiente"),
                ("back", "Voltar"),
            ]
        )

    def _show_scope(self, next_mode: str, title: str) -> None:
        self._mode = next_mode
        self._set_status(title)
        self._set_options(
            [
                ("scope:global", "Global (SQLite da máquina)"),
                ("scope:project", "Projeto (SQLite por project_id)"),
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
            if option_id == "model":
                self._show_scope("scope_model", "Escopo do modelo")
            elif option_id == "permissions":
                self._show_scope("scope_permissions", "Escopo das permissões")
            elif option_id == "workflows":
                self._show_scope("scope_workflows", "Escopo dos workflows")
            elif option_id == "doctor":
                self._run_doctor()
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
            return
        if self._mode == "pick_agent" and option_id.startswith("agent:"):
            self._save_workflow_agent(option_id.split(":", 1)[1])

    @work(thread=True)
    def _load_models(self, *, for_workflow: bool = False) -> None:
        self.app.call_from_thread(self._set_status, "Carregando modelos…")
        models = collect_available_models(self._cwd)
        def apply() -> None:
            self._mode = "pick_model"
            self._set_status("Escolha o modelo" + (" do workflow" if for_workflow else ""))
            self._set_options([(f"model:{m}", m) for m in models] + [("back", "Voltar")])
        self.app.call_from_thread(apply)

    def _show_permissions(self) -> None:
        self._mode = "pick_permission"
        self._set_status("Escolha a política de permissões")
        self._set_options(
            [(f"policy:{key}", label) for key, label in permission_choices()]
            + [("back", "Voltar")]
        )

    def _show_workflows(self) -> None:
        ensure_project_workflows(self._cwd)
        self._mode = "pick_workflow"
        self._set_status("Escolha o workflow")
        options: list[tuple[str, str]] = []
        for spec in SPEC_TYPES:
            resolved = resolve_config(self._cwd, workflow=spec.id)
            options.append(
                (
                    f"workflow:{spec.id}",
                    f"{spec.label} — {resolved.agent_name} · {resolved.model}",
                )
            )
        options.append(("back", "Voltar"))
        self._set_options(options)

    def _show_workflow_fields(self) -> None:
        self._mode = "workflow_fields"
        self._set_status(f"Workflow: {self._workflow_id}")
        self._set_options(
            [
                ("wf_agent", "Agente"),
                ("wf_model", "Modelo"),
                ("back", "Voltar"),
            ]
        )

    def _show_agents(self) -> None:
        resolved = resolve_config(self._cwd, workflow=self._workflow_id)
        self._mode = "pick_agent"
        self._set_status("Escolha o agente")
        options = [
            (f"agent:{name}", f"{name} ({agent.binary})")
            for name, agent in resolved.agents.items()
        ]
        options.append(("back", "Voltar"))
        self._set_options(options)

    def _save_model(self, model: str) -> None:
        if self._workflow_id and self._scope:
            if self._scope == "global":
                path = update_global_workflow(self._workflow_id, model=model)
            else:
                path = update_project_workflow(self._cwd, self._workflow_id, model=model)
            self._set_status(f"Modelo do workflow salvo: {model} ({path})")
            self._show_workflow_fields()
            return
        if self._scope == "global":
            if not global_config_exists():
                self._set_status("Config global não encontrada. Rode Configurar Pulse.")
                self._show_root()
                return
            path = update_global_defaults(model=model)
        else:
            path = update_project_defaults(self._cwd, model=model)
        self._set_status(f"Modelo salvo: {model} ({path})")
        self._show_root()

    def _save_permission(self, policy: str) -> None:
        label = PERMISSION_LABELS.get(policy, policy)
        if self._scope == "global":
            if not global_config_exists():
                self._set_status("Config global não encontrada. Rode Configurar Pulse.")
                self._show_root()
                return
            path = update_global_defaults(permission_policy=policy)
        else:
            path = update_project_defaults(self._cwd, permission_policy=policy)
        self._set_status(f"Permissões salvas: {label} ({path})")
        self._show_root()

    def _save_workflow_agent(self, agent: str) -> None:
        if not self._workflow_id or not self._scope:
            return
        if self._scope == "global":
            path = update_global_workflow(self._workflow_id, agent=agent)
        else:
            path = update_project_workflow(self._cwd, self._workflow_id, agent=agent)
        self._set_status(f"Agente do workflow salvo: {agent} ({path})")
        self._show_workflow_fields()

    def _run_doctor(self) -> None:
        checks = run_environment_checks()
        lines = []
        for check in checks:
            mark = "ok" if check.status == "ok" else check.status.upper()
            lines.append(f"[{mark}] {check.message}")
        cfg = load_global_config()
        if cfg:
            lines.append(f"[ok] Config global · modelo={cfg.model}")
        project = load_project_config(self._cwd)
        if project is not None:
            lines.append(f"[ok] Config projeto · {project.source_file}")
        self._set_status("\n".join(lines) if lines else "Nenhum check")
        self._show_root()
