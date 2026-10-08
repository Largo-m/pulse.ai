from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.client.engine_client import EngineClient
from pulse.config import (
    global_config_exists,
    init_project_config,
    load_global_config,
    mark_onboarding_complete,
    project_config_exists,
)
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.model_catalog import DEFAULT_MODELS, collect_available_models
from pulse.doctor.checks import run_agent_checks
from pulse.runtimes import DEFAULT_RUNTIME_ID, all_runtimes, get_runtime
from pulse.store.paths import GLOBAL_DB_FILE
from pulse.tui import strings


class OnboardingScreen(Screen[int]):
    BINDINGS = [("escape", "cancel", strings.CANCEL), ("q", "cancel", strings.CANCEL)]

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
            yield Static(strings.ONBOARD_TITLE, classes="onboard-title")
            yield Static(strings.ENVIRONMENT, id="onboard-status", classes="onboard-hint")
            yield OptionList(id="onboard-options")
            yield Input(
                placeholder=strings.ONBOARD_WORKSPACE_PLACEHOLDER,
                id="onboard-input",
            )
            yield Static("", id="onboard-report", classes="onboard-report")
            yield Static(strings.ONBOARD_HINT_KEYS, classes="onboard-hint-keys")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#onboard-input", Input).display = False
        self._set_report("")
        if global_config_exists() and not self._force:
            existing = load_global_config()
            if existing and existing.is_onboarded:
                self._step = "overwrite"
                self._set_status(strings.ONBOARD_CONFIG_EXISTS)
                self._set_report(str(GLOBAL_DB_FILE))
                self._set_options(
                    [
                        ("overwrite_yes", strings.ONBOARD_RECONFIGURE),
                        ("overwrite_no", strings.ONBOARD_KEEP),
                    ]
                )
                return
        self._ask_runtime()

    def _ask_runtime(self) -> None:
        self._step = "runtime"
        self._set_status(strings.ONBOARD_DEFAULT_AGENT)
        self._set_report("")
        self._set_options(
            [
                (
                    f"runtime:{item.id}",
                    strings.ONBOARD_RUNTIME_OPTION.format(label=item.label, binary=item.binary),
                )
                for item in all_runtimes()
            ]
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
        self._set_status(strings.ONBOARD_ENVIRONMENT_FOR.format(runtime=self._runtime.label))
        self._set_report("\n".join(f"[{c.status}] {c.message}" for c in checks))
        if any(check.status == "fail" for check in cli_checks):
            self._step = "agent_fail"
            self._set_options(
                [("quit", strings.ONBOARD_QUIT_INSTALL.format(hint=self._runtime.install_hint))]
            )
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
            ("auth_login", strings.ONBOARD_RETRY if retry else self._runtime.login_label),
            ("auth_skip", strings.ONBOARD_AUTH_LATER.format(env_var=self._runtime.auth_env_var)),
            ("quit", strings.CANCEL),
        ]

    def _ask_workspace(self) -> None:
        existing = load_global_config()
        if existing:
            self._workspace = existing.workspace_dir
        self._step = "workspace"
        self._set_status(strings.ONBOARD_WORKSPACE_STATUS)
        self._set_report("")
        self._hide_options()
        self._show_input(str(self._workspace), strings.ONBOARD_WORKSPACE_INPUT)

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
                    strings.ONBOARD_EXPORT_KEY.format(env_var=self._runtime.auth_env_var)
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
            self._set_status(strings.ONBOARD_WORKSPACE_STATUS)
            self._set_report(strings.ONBOARD_INVALID_DIRECTORY)
            return
        self._workspace = path.resolve()
        self._hide_input()
        self._run_acp_probe()

    @work(thread=True)
    def _do_login(self) -> None:
        self.app.call_from_thread(
            self._set_status, strings.ONBOARD_OPENING_LOGIN.format(login=self._runtime.login_label)
        )
        code = self._runtime.login()
        auth = run_agent_checks(self._runtime.id)[-1]

        def apply() -> None:
            if code != 0 or auth.status == "fail":
                self._set_status(strings.ONBOARD_LOGIN_FAILED)
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
        self.app.call_from_thread(self._set_status, strings.ONBOARD_TESTING_ACP)
        probe = self._probe_through_engine()
        models = [str(model) for model in probe.get("available_models") or []]
        if not models:
            models = collect_available_models(self._workspace, agent_name=self._runtime.id)
        self._models = models or list(self._runtime.default_models) or list(DEFAULT_MODELS)
        self._acp_ok = bool(probe.get("ok"))
        message = str(probe.get("message") or "")

        def apply() -> None:
            if self._acp_ok:
                self._set_status(strings.ONBOARD_ACP_CONNECTION)
                self._set_report(message)
                self._finish()
                return
            self._step = "acp_fail"
            self._set_status(strings.ONBOARD_ACP_CONNECTION)
            self._set_report(str(probe.get("error") or message))
            self._set_options(
                [
                    ("acp_continue", strings.ONBOARD_CONTINUE_ANYWAY),
                    ("quit", strings.CANCEL),
                ]
            )

        self.app.call_from_thread(apply)

    def _probe_through_engine(self) -> dict[str, Any]:
        """An unreachable engine is a failed probe, so the user can still continue."""
        client = EngineClient()
        try:
            client.ensure_daemon()
            return client.acp_probe(workspace=self._workspace, runtime=self._runtime.id)
        except (RuntimeError, httpx.HTTPError) as error:
            return {"ok": False, "message": strings.ONBOARD_ENGINE_UNAVAILABLE, "error": str(error)}
        finally:
            client.close()

    def _ask_model(self) -> None:
        self._step = "model"
        self._set_status(strings.ONBOARD_MODEL)
        unique: list[str] = []
        for item in self._models:
            if item not in unique:
                unique.append(item)
        self._set_options([(f"model:{m}", m) for m in unique])

    def _ask_policy(self) -> None:
        self._step = "policy"
        self._set_status(strings.ONBOARD_POLICY)
        self._set_options(
            [(f"policy:{key}", strings.PERMISSION_LABELS[key]) for key in PERMISSION_POLICIES]
        )

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
        self._set_status(strings.ONBOARD_READY)
        self._set_report(strings.ONBOARD_CONFIG_SAVED.format(path=config_path))
        self.dismiss(0)
