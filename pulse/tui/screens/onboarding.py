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
    project_config_file,
)
from pulse.config.model_catalog import DEFAULT_MODELS, collect_available_models, permission_choices
from pulse.doctor.checks import check_agent_in_path, check_auth, find_agent_binary
from pulse.doctor.report import run_agent_login


class OnboardingScreen(Screen[int]):
    BINDINGS = [("escape", "cancel", "Cancelar"), ("q", "cancel", "Cancelar")]

    def __init__(self, *, force: bool = False) -> None:
        super().__init__()
        self._force = force
        self._step = "intro"
        self._workspace = Path.cwd()
        self._model = "Auto"
        self._policy = "ask"
        self._auth_method = "cursor_login"
        self._acp_ok = False
        self._models: list[str] = list(DEFAULT_MODELS)

    def compose(self) -> ComposeResult:
        with Vertical(id="onboard-content"):
            yield Static("Configurar Pulse", classes="home-brand")
            yield Static("", id="onboard-status", classes="home-sub")
            yield OptionList(id="onboard-options")
            yield Input(
                placeholder="Caminho do workspace…",
                id="onboard-input",
                classes="-hidden",
            )
            yield Static("Enter confirma · Esc cancela", classes="home-hint")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#onboard-input", Input).display = False
        if global_config_exists() and not self._force:
            existing = load_global_config()
            if existing and existing.is_onboarded:
                self._step = "overwrite"
                self._set_status(f"Config já existe em {GLOBAL_CONFIG_FILE}. Reconfigurar?")
                self._set_options(
                    [
                        ("overwrite_yes", "Sim, reconfigurar"),
                        ("overwrite_no", "Não, manter"),
                    ]
                )
                return
        self._start_checks()

    def action_cancel(self) -> None:
        self.dismiss(130)

    def _set_status(self, text: str) -> None:
        self.query_one("#onboard-status", Static).update(text)

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
        agent_check = check_agent_in_path()
        auth_check = check_auth()
        lines = [
            f"[{agent_check.status}] {agent_check.message}",
            f"[{auth_check.status}] {auth_check.message}",
        ]
        self._set_status("\n".join(lines))
        if agent_check.status != "ok":
            self._step = "agent_fail"
            self._set_options([("quit", "Sair e instalar o Cursor CLI")])
            return
        if auth_check.status != "ok":
            self._step = "auth"
            self._set_options(
                [
                    ("auth_login", "Executar `agent login`"),
                    ("auth_skip", "Usar CURSOR_API_KEY depois"),
                    ("quit", "Cancelar"),
                ]
            )
            return
        if auth_check.detail == "api_key":
            self._auth_method = "api_key"
        self._ask_workspace()

    def _ask_workspace(self) -> None:
        existing = load_global_config()
        if existing:
            self._workspace = existing.workspace_dir
        self._step = "workspace"
        self._set_status("Diretório padrão do workspace")
        self._hide_options()
        self._show_input(str(self._workspace), "Caminho absoluto do workspace")

    @on(OptionList.OptionSelected, "#onboard-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = str(event.option_id or "")
        if option_id in {"quit", "overwrite_no"}:
            self.dismiss(0 if option_id == "overwrite_no" else 1)
            return
        if option_id == "overwrite_yes":
            self._start_checks()
            return
        if self._step == "auth":
            if option_id == "auth_login":
                self._do_login()
            elif option_id == "auth_skip":
                self._set_status("Exporte CURSOR_API_KEY e rode `pulse` de novo.")
                self.dismiss(1)
            return
        if self._step == "acp_fail" and option_id == "acp_continue":
            self._ask_model()
            return
        if self._step == "model" and option_id.startswith("model:"):
            self._model = option_id.split(":", 1)[1]
            self._ask_policy()
            return
        if self._step == "policy" and option_id.startswith("policy:"):
            self._policy = option_id.split(":", 1)[1]
            self._finish()

    @on(Input.Submitted, "#onboard-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self._step != "workspace":
            return
        text = event.value.strip()
        if not text:
            return
        path = Path(text).expanduser()
        if not path.is_dir():
            self._set_status("Diretório inválido. Escolha uma pasta existente.")
            return
        self._workspace = path.resolve()
        self._hide_input()
        self._run_acp_probe()

    @work(thread=True)
    def _do_login(self) -> None:
        self.app.call_from_thread(self._set_status, "Abrindo `agent login`…")
        code = run_agent_login()
        auth = check_auth()
        def apply() -> None:
            if code != 0 or auth.status != "ok":
                self._set_status("Login não concluído.")
                self._set_options(
                    [
                        ("auth_login", "Tentar de novo"),
                        ("auth_skip", "Usar CURSOR_API_KEY depois"),
                        ("quit", "Cancelar"),
                    ]
                )
                return
            self._auth_method = "api_key" if auth.detail == "api_key" else "cursor_login"
            self._ask_workspace()
        self.app.call_from_thread(apply)

    @work(thread=True)
    def _run_acp_probe(self) -> None:
        self.app.call_from_thread(self._set_status, "Testando conexão ACP…")
        probe = probe_acp_connection(cwd=str(self._workspace))
        models = list(probe.available_models or [])
        if not models:
            models = collect_available_models(self._workspace)
        self._models = models or list(DEFAULT_MODELS)
        self._acp_ok = probe.success

        def apply() -> None:
            if probe.success:
                self._set_status(f"✓ {probe.message}")
                self._ask_model()
                return
            self._step = "acp_fail"
            self._set_status(f"✗ {probe.error or probe.message}")
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
        agent_binary = find_agent_binary() or "agent"
        config_path = mark_onboarding_complete(
            agent_binary=agent_binary,
            acp_command=[agent_binary, "acp"],
            auth_method=self._auth_method,
            workspace_dir=self._workspace,
            model=self._model,
            permission_policy=self._policy,
            acp_test_passed=self._acp_ok,
        )
        project_path = project_config_file(self._workspace)
        if not project_path.is_file():
            init_project_config(self._workspace)
        self._set_status(f"✓ Config salvo em {config_path}")
        self.dismiss(0)
