from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.acp.client import probe_acp_connection
from pulse.config import (
    GLOBAL_CONFIG_FILE,
    global_config_exists,
    init_project_config,
    load_global_config,
    mark_onboarding_complete,
    project_config_exists,
)
from pulse.config.model_catalog import DEFAULT_MODELS, collect_available_models, permission_choices
from pulse.doctor.checks import run_agent_checks
from pulse.runtimes import DEFAULT_RUNTIME_ID, all_runtimes, get_runtime


class OnboardingScreen(Screen[int]):
    BINDINGS = [("escape", "cancel", "Cancelar"), ("q", "cancel", "Cancelar")]

    def __init__(self, *, force: bool = False) -> None:
        super().__init__()
        self._force = force
        self._step = "intro"
        self._workspace = Path.cwd()
        self._model = "Auto"
        self._policy = "ask"
        self._runtime = get_runtime(DEFAULT_RUNTIME_ID)
        self._auth_method = self._runtime.auth_method_label
        self._acp_ok = False
        self._models: list[str] = list(DEFAULT_MODELS)

    def compose(self) -> ComposeResult:
        with Vertical(id="onboard-content"):
            yield Static("CONFIGURAR PULSE", classes="onboard-title")
            yield Static("Ambiente", id="onboard-status", classes="onboard-hint")
            yield OptionList(id="onboard-options")
            yield Input(
                placeholder="Caminho do workspace…",
                id="onboard-input",
            )
            yield Static("", id="onboard-report", classes="onboard-report")
            yield Static("Enter confirma  ·  Esc cancela", classes="onboard-hint-keys")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#onboard-input", Input).display = False
        self._set_report("")
        if global_config_exists() and not self._force:
            existing = load_global_config()
            if existing and existing.is_onboarded:
                self._step = "overwrite"
                self._set_status("Config já existe")
                self._set_report(str(GLOBAL_CONFIG_FILE))
                self._set_options(
                    [
                        ("overwrite_yes", "Sim — reconfigurar"),
                        ("overwrite_no", "Não — manter"),
                    ]
                )
                return
        self._ask_runtime()

    def _ask_runtime(self) -> None:
        self._step = "runtime"
        self._set_status("Agente padrão")
        self._set_report("")
        self._set_options(
            [(f"runtime:{item.id}", f"{item.label} — `{item.binary}`") for item in all_runtimes()]
        )

    def action_cancel(self) -> None:
        self.dismiss(130)

    def _set_status(self, text: str) -> None:
        self.query_one("#onboard-status", Static).update(text)

    def _set_report(self, text: str) -> None:
        widget = self.query_one("#onboard-report", Static)
        widget.update(text)
        widget.display = bool(text)

    def _set_options(self, options: list[tuple[str, str]]) -> None:
        widget = self.query_one("#onboard-options", OptionList)
        widget.clear_options()
        widget.display = True
        for option_id, label in options:
            widget.add_option(Option(label, id=option_id))
        widget.focus()

    def _hide_options(self) -> None:
        self.query_one("#onboard-options", OptionList).display = False

    def _show_input(self, value: str, placeholder: str) -> None:
        prompt = self.query_one("#onboard-input", Input)
        prompt.value = value
        prompt.placeholder = placeholder
        prompt.display = True
        prompt.focus()

    def _hide_input(self) -> None:
        prompt = self.query_one("#onboard-input", Input)
        prompt.display = False

    def _start_checks(self) -> None:
        checks = run_agent_checks(self._runtime.id)
        auth_check = checks[-1]
        cli_checks = checks[:-1]
        self._set_status(f"Ambiente — {self._runtime.label}")
        self._set_report("\n".join(f"[{c.status}] {c.message}" for c in checks))
        if any(check.status == "fail" for check in cli_checks):
            self._step = "agent_fail"
            self._set_options([("quit", f"Sair — {self._runtime.install_hint}")])
            return
        if auth_check.status == "fail":
            self._step = "auth"
            self._set_options(self._auth_options())
            return
        if auth_check.detail == "api_key":
            self._auth_method = "api_key"
        self._ask_workspace()

    def _auth_options(self, retry: bool = False) -> list[tuple[str, str]]:
        return [
            ("auth_login", "Tentar de novo" if retry else self._runtime.login_label),
            ("auth_skip", f"Usar {self._runtime.auth_env_var} depois"),
            ("quit", "Cancelar"),
        ]

    def _ask_workspace(self) -> None:
        existing = load_global_config()
        if existing:
            self._workspace = existing.workspace_dir
        self._step = "workspace"
        self._set_status("Diretório padrão do workspace")
        self._set_report("")
        self._hide_options()
        self._show_input(str(self._workspace), "Caminho absoluto do workspace")

    @on(OptionList.OptionSelected, "#onboard-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = str(event.option_id or "")
        if option_id in {"quit", "overwrite_no"}:
            self.dismiss(0 if option_id == "overwrite_no" else 1)
            return
        if option_id == "overwrite_yes":
            self._ask_runtime()
            return
        if option_id.startswith("runtime:"):
            self._runtime = get_runtime(option_id.split(":", 1)[1])
            self._auth_method = self._runtime.auth_method_label
            self._start_checks()
            return
        if self._step == "auth":
            if option_id == "auth_login":
                self._do_login()
            elif option_id == "auth_skip":
                self._set_status(
                    f"Exporte {self._runtime.auth_env_var} e rode `pulse` de novo."
                )
                self._set_report("")
                self.dismiss(1)
            return
        if self._step == "acp_fail" and option_id == "acp_continue":
            self._finish()
            return

    @on(Input.Submitted, "#onboard-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._step != "workspace":
            return
        text = event.value.strip()
        if not text:
            return
        path = Path(text).expanduser()
        if not path.is_dir():
            self._set_status("Diretório padrão do workspace")
            self._set_report("Diretório inválido. Escolha uma pasta existente.")
            return
        self._workspace = path.resolve()
        self._hide_input()
        self._run_acp_probe()

    @work(thread=True)
    def _do_login(self) -> None:
        self.app.call_from_thread(self._set_status, f"Abrindo {self._runtime.login_label}…")
        code = self._runtime.login()
        auth = run_agent_checks(self._runtime.id)[-1]

        def apply() -> None:
            if code != 0 or auth.status == "fail":
                self._set_status("Login não concluído")
                self._set_report(auth.message)
                self._set_options(self._auth_options(retry=True))
                return
            self._auth_method = (
                "api_key" if auth.detail == "api_key" else self._runtime.auth_method_label
            )
            self._ask_workspace()
        self.app.call_from_thread(apply)

    @work(thread=True)
    def _run_acp_probe(self) -> None:
        self.app.call_from_thread(self._set_status, "Testando conexão ACP…")
        probe = probe_acp_connection(
            command=list(self._runtime.acp_command),
            cwd=str(self._workspace),
        )
        models = list(probe.available_models or [])
        if not models:
            models = collect_available_models(self._workspace, agent_name=self._runtime.id)
        self._models = models or list(self._runtime.default_models) or list(DEFAULT_MODELS)
        self._acp_ok = probe.success

        def apply() -> None:
            if probe.success:
                self._set_status("Conexão ACP")
                self._set_report(probe.message)
                self._finish()
                return
            self._step = "acp_fail"
            self._set_status("Conexão ACP")
            self._set_report(probe.error or probe.message)
            self._set_options(
                [
                    ("acp_continue", "Continuar mesmo assim"),
                    ("quit", "Cancelar"),
                ]
            )

        self.app.call_from_thread(apply)

    def _ask_model(self) -> None:
        self._step = "model"
        self._set_status("Modelo preferido")
        unique: list[str] = []
        for item in self._models:
            if item not in unique:
                unique.append(item)
        self._set_options([(f"model:{m}", m) for m in unique])

    def _ask_policy(self) -> None:
        self._step = "policy"
        self._set_status("Política de permissões")
        self._set_options([(f"policy:{key}", label) for key, label in permission_choices()])

    def _finish(self) -> None:
        config_path = mark_onboarding_complete(
            agent_binary=self._runtime.find_binary() or self._runtime.binary,
            acp_command=list(self._runtime.acp_command),
            auth_method=self._auth_method,
            workspace_dir=self._workspace,
            model=self._model,
            permission_policy=self._policy,
            acp_test_passed=self._acp_ok,
            default_agent=self._runtime.id,
        )
        if not project_config_exists(self._workspace):
            init_project_config(self._workspace)
        self._set_status("Pronto")
        self._set_report(f"Config salvo em {config_path}")
        self.dismiss(0)
