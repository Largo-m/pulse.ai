from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse.client.runtime_login import run_login
from pulse.tui import engine, strings
from pulse.tui.engine import EngineError, EngineUnavailable, RuntimeInfo, SetupState

DEFAULT_MODEL = "Auto"
DEFAULT_POLICY = "ask"


class OnboardingScreen(Screen[int]):
    BINDINGS = [("escape", "cancel", strings.CANCEL), ("q", "cancel", strings.CANCEL)]

    def __init__(self, *, force: bool = False) -> None:
        super().__init__()
        self._force = force
        self._step = "intro"
        self._workspace = Path.cwd()
        self._model = DEFAULT_MODEL
        self._policy = DEFAULT_POLICY
        self._runtimes: dict[str, RuntimeInfo] = {}
        self._runtime: RuntimeInfo | None = None
        self._setup: SetupState | None = None
        self._auth_method = ""
        self._acp_ok = False

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
        try:
            self._setup = engine.setup_state(self._workspace)
            default_id, runtimes = engine.runtimes()
        except EngineError as error:
            self._step = "engine_fail"
            self._set_status(error.headline)
            self._set_report(str(error))
            self._set_options([("quit", strings.CANCEL)])
            return
        self._runtimes = {runtime.id: runtime for runtime in runtimes}
        self._choose(default_id)
        if self._setup.onboarded and not self._force:
            self._step = "overwrite"
            self._set_status(strings.ONBOARD_CONFIG_EXISTS)
            self._set_report(self._setup.database)
            self._set_options(
                [
                    ("overwrite_yes", strings.ONBOARD_RECONFIGURE),
                    ("overwrite_no", strings.ONBOARD_KEEP),
                ]
            )
            return
        self._ask_runtime()

    def _choose(self, runtime_id: str) -> RuntimeInfo:
        runtime = self._runtimes.get(runtime_id) or next(iter(self._runtimes.values()))
        self._runtime = runtime
        self._auth_method = runtime.auth_method_label
        return runtime

    def _chosen(self) -> RuntimeInfo:
        if self._runtime is None:
            raise EngineUnavailable("no runtime loaded")
        return self._runtime

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
                for item in self._runtimes.values()
            ]
        )

    def action_cancel(self) -> None:
        self.dismiss(130)

    def _set_status(self, text: str) -> None:
        self.query_one("#onboard-status", Static).update(text)

    def _set_report(self, text: str) -> None:
        widget = self.query_one("#onboard-report", Static)
        # Plain text: check tags like `[fail]` and agent errors are not Rich markup.
        widget.update(Text(text))
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
        runtime = self._chosen()
        checks = engine.runtime_checks(runtime.id)
        auth_check = checks[-1]
        cli_checks = checks[:-1]
        self._set_status(strings.ONBOARD_ENVIRONMENT_FOR.format(runtime=runtime.label))
        self._set_report("\n".join(f"[{c.status}] {c.message}" for c in checks))
        if any(check.status == "fail" for check in cli_checks):
            self._step = "agent_fail"
            self._set_options(
                [("quit", strings.ONBOARD_QUIT_INSTALL.format(hint=runtime.install_hint))]
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
        runtime = self._chosen()
        return [
            ("auth_login", strings.ONBOARD_RETRY if retry else _login_label(runtime)),
            ("auth_skip", strings.ONBOARD_AUTH_LATER.format(env_var=runtime.auth_env_var)),
            ("quit", strings.CANCEL),
        ]

    def _ask_workspace(self) -> None:
        if self._setup is not None and self._setup.workspace_dir:
            self._workspace = Path(self._setup.workspace_dir)
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
        try:
            self._route_option(option_id)
        except EngineError as error:
            self._set_status(error.headline)
            self._set_report(str(error))

    def _route_option(self, option_id: str) -> None:
        if option_id.startswith("runtime:"):
            self._choose(option_id.split(":", 1)[1])
            self._start_checks()
            return
        if self._step == "auth":
            if option_id == "auth_login":
                self._do_login()
            elif option_id == "auth_skip":
                self._set_status(
                    strings.ONBOARD_EXPORT_KEY.format(env_var=self._chosen().auth_env_var)
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
        runtime = self._chosen()
        self.app.call_from_thread(
            self._set_status, strings.ONBOARD_OPENING_LOGIN.format(login=_login_label(runtime))
        )
        code = run_login(runtime.login_command)
        try:
            auth = engine.runtime_checks(runtime.id)[-1]
        except EngineError as error:
            self.app.call_from_thread(self._login_unverified, error)
            return

        def apply() -> None:
            if code != 0 or auth.status == "fail":
                self._set_status(strings.ONBOARD_LOGIN_FAILED)
                self._set_report(auth.message)
                self._set_options(self._auth_options(retry=True))
                return
            self._auth_method = "api_key" if auth.detail == "api_key" else runtime.auth_method_label
            self._ask_workspace()

        self.app.call_from_thread(apply)

    def _login_unverified(self, error: EngineError) -> None:
        self._set_status(error.headline)
        self._set_report(str(error))
        self._set_options(self._auth_options(retry=True))

    @work(thread=True)
    def _run_acp_probe(self) -> None:
        self.app.call_from_thread(self._set_status, strings.ONBOARD_TESTING_ACP)
        runtime = self._chosen()
        probe = self._probe_through_engine(runtime)
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

    def _probe_through_engine(self, runtime: RuntimeInfo) -> dict[str, Any]:
        """An unreachable engine is a failed probe, so the user can still continue."""
        try:
            return engine.acp_probe(self._workspace, runtime.id)
        except EngineError as error:
            return {"ok": False, "message": error.headline, "error": str(error)}

    def _finish(self) -> None:
        try:
            config_path = engine.complete_onboarding(
                runtime_id=self._chosen().id,
                workspace=self._workspace,
                model=self._model,
                permission_policy=self._policy,
                auth_method=self._auth_method,
                acp_test_passed=self._acp_ok,
            )
        except EngineError as error:
            self._set_status(error.headline)
            self._set_report(str(error))
            self._set_options([("quit", strings.CANCEL)])
            return
        self._set_status(strings.ONBOARD_READY)
        self._set_report(strings.ONBOARD_CONFIG_SAVED.format(path=config_path))
        self.dismiss(0)


def _login_label(runtime: RuntimeInfo) -> str:
    """The action that opens the runtime's own login; empty when it has none."""
    if not runtime.login_command:
        return ""
    return strings.ONBOARD_RUN_LOGIN.format(command=" ".join(runtime.login_command))
