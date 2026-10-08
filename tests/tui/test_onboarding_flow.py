"""The onboarding wizard end to end: environment checks, login, workspace and ACP probe.

The runtime's checks, its login and the daemon probe are the boundaries; they are
replaced by scripted fakes. Configuration lands in the real (per-test) SQLite.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.config import load_global_config, mark_onboarding_complete, project_config_exists
from pulse.doctor.checks import CheckResult
from pulse.runtimes import DEFAULT_RUNTIME_ID, all_runtimes, get_runtime
from pulse.tui import strings
from pulse.tui.screens import onboarding
from pulse.tui.screens.onboarding import OnboardingScreen
from pulse.tui.theme import COCKPIT_CSS

CANCELLED = 130

OK_CLI = CheckResult(name="cli", status="ok", message="agent 1.0")
MISSING_CLI = CheckResult(name="cli", status="fail", message="agent not found")
API_KEY = CheckResult(name="auth", status="ok", message="key set", detail="api_key")
LOGGED_IN = CheckResult(name="auth", status="ok", message="logged in")
LOGGED_OUT = CheckResult(name="auth", status="fail", message="not logged in")


class _Engine:
    """The daemon at the HTTP boundary: answers the ACP probe with `probe`."""

    probe: dict[str, object] = {}
    asked: list[dict[str, object]] = []

    def __init__(self, **_kwargs: object) -> None:
        pass

    def ensure_daemon(self) -> None:
        return None

    def acp_probe(self, *, workspace: Path, runtime: str) -> dict[str, object]:
        type(self).asked.append({"workspace": workspace, "runtime": runtime})
        return type(self).probe

    def close(self) -> None:
        return None


class _Env:
    """Scripted environment: each `run_agent_checks` call pops the next check list."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, checks: list[list[CheckResult]]) -> None:
        self.checks = checks
        self.logins: list[int] = []
        self.login_codes: list[int] = []
        runtime = get_runtime(DEFAULT_RUNTIME_ID)
        monkeypatch.setattr(onboarding, "run_agent_checks", self._run_checks)
        monkeypatch.setattr(runtime, "login", self._login)
        monkeypatch.setattr(runtime, "find_binary", lambda: "/opt/bin/agent")
        monkeypatch.setattr(onboarding, "EngineClient", _Engine)
        monkeypatch.setattr(_Engine, "probe", {"ok": True, "message": "connected"})
        monkeypatch.setattr(_Engine, "asked", [])
        monkeypatch.setattr(onboarding, "collect_available_models", lambda *_a, **_k: [])

    def _run_checks(self, _runtime: str) -> list[CheckResult]:
        return self.checks.pop(0)

    def _login(self) -> int:
        code = self.login_codes.pop(0)
        self.logins.append(code)
        return code


def _app(screen: OnboardingScreen, results: list[int | None]):
    from textual.app import App

    class Harness(App[None]):
        CSS = COCKPIT_CSS

        def on_mount(self) -> None:
            self.push_screen(screen, callback=results.append)

    return Harness()


def _option_ids(screen: OnboardingScreen) -> list[str]:
    from textual.widgets import OptionList

    options = screen.query_one("#onboard-options", OptionList)
    return [str(options.get_option_at_index(index).id) for index in range(options.option_count)]


async def _choose(pilot, screen: OnboardingScreen, option_id: str) -> None:
    from textual.widgets import OptionList

    options = screen.query_one("#onboard-options", OptionList)
    options.focus()
    options.highlighted = options.get_option_index(option_id)
    await pilot.press("enter")
    await pilot.pause()


async def _submit(pilot, screen: OnboardingScreen, text: str) -> None:
    from textual.widgets import Input

    field = screen.query_one("#onboard-input", Input)
    field.value = text
    field.focus()
    await pilot.press("enter")
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


def _status(screen: OnboardingScreen) -> str:
    return str(screen.query_one("#onboard-status").render())


def _report(screen: OnboardingScreen) -> str:
    return str(screen.query_one("#onboard-report").render())


def test_first_run_checks_asks_the_workspace_probes_and_saves_the_config(monkeypatch, tmp_path):
    """The happy path persists the machine config and registers the chosen project."""
    from textual.widgets import Input

    env = _Env(monkeypatch, [[OK_CLI, API_KEY]])
    monkeypatch.setattr(_Engine, "probe", {"ok": True, "available_models": ["m1"]})
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "work"
    workspace.mkdir()
    results: list[int | None] = []
    screen = OnboardingScreen()

    async def run() -> None:
        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            assert _status(screen) == strings.ONBOARD_DEFAULT_AGENT
            assert _option_ids(screen) == [f"runtime:{item.id}" for item in all_runtimes()]

            await _choose(pilot, screen, f"runtime:{DEFAULT_RUNTIME_ID}")
            field = screen.query_one("#onboard-input", Input)
            assert field.display is True
            assert field.value == str(tmp_path)
            assert _status(screen) == strings.ONBOARD_WORKSPACE_STATUS

            await _submit(pilot, screen, "   ")
            assert results == [], "a blank path is ignored"
            await _submit(pilot, screen, str(tmp_path / "missing"))
            assert _report(screen) == strings.ONBOARD_INVALID_DIRECTORY
            assert results == []

            await _submit(pilot, screen, str(workspace))

    asyncio.run(run())

    assert results == [0]
    assert env.checks == []
    assert _Engine.asked == [{"workspace": workspace.resolve(), "runtime": DEFAULT_RUNTIME_ID}]
    saved = load_global_config()
    assert saved is not None
    assert saved.is_onboarded
    assert saved.default_agent == DEFAULT_RUNTIME_ID
    assert saved.auth_method == "api_key"
    assert saved.agent_binary == "/opt/bin/agent"
    assert saved.workspace_dir == workspace.resolve()
    assert saved.acp_test_passed is True
    assert project_config_exists(workspace)


def test_a_missing_agent_cli_stops_with_the_install_hint(monkeypatch, tmp_path):
    """Without the binary nothing else can work; the only way out says how to install it."""
    _Env(monkeypatch, [[MISSING_CLI, LOGGED_OUT]])
    results: list[int | None] = []
    screen = OnboardingScreen()
    runtime = get_runtime(DEFAULT_RUNTIME_ID)

    async def run() -> None:
        from textual.widgets import OptionList

        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await _choose(pilot, screen, f"runtime:{DEFAULT_RUNTIME_ID}")
            assert _status(screen) == strings.ONBOARD_ENVIRONMENT_FOR.format(runtime=runtime.label)
            # The status tags are text, not Rich markup that would swallow them.
            assert _report(screen).splitlines() == [
                f"[{MISSING_CLI.status}] agent not found",
                f"[{LOGGED_OUT.status}] not logged in",
            ]
            assert _option_ids(screen) == ["quit"]
            label = str(screen.query_one("#onboard-options", OptionList).get_option("quit").prompt)
            assert label == strings.ONBOARD_QUIT_INSTALL.format(hint=runtime.install_hint)

            await _choose(pilot, screen, "quit")

    asyncio.run(run())

    assert results == [1]
    assert load_global_config() is None


def test_a_failed_login_offers_a_retry_and_a_good_one_moves_on(monkeypatch, tmp_path):
    """The login runs off the UI thread; failure keeps the user on the auth step."""
    from textual.widgets import Input

    env = _Env(
        monkeypatch,
        [[OK_CLI, LOGGED_OUT], [OK_CLI, LOGGED_OUT], [OK_CLI, LOGGED_IN]],
    )
    env.login_codes = [0, 0]
    results: list[int | None] = []
    screen = OnboardingScreen()

    async def run() -> None:
        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await _choose(pilot, screen, f"runtime:{DEFAULT_RUNTIME_ID}")
            assert _option_ids(screen) == ["auth_login", "auth_skip", "quit"]

            await _choose(pilot, screen, "auth_login")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert _status(screen) == strings.ONBOARD_LOGIN_FAILED
            assert _report(screen) == "not logged in"
            assert _option_ids(screen) == ["auth_login", "auth_skip", "quit"]

            await _choose(pilot, screen, "auth_login")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert _status(screen) == strings.ONBOARD_WORKSPACE_STATUS
            assert screen.query_one("#onboard-input", Input).display is True

    asyncio.run(run())

    assert env.logins == [0, 0]
    assert results == []


def test_skipping_login_tells_which_key_to_export_and_ends_the_wizard(monkeypatch):
    _Env(monkeypatch, [[OK_CLI, LOGGED_OUT]])
    results: list[int | None] = []
    screen = OnboardingScreen()

    async def run() -> None:
        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await _choose(pilot, screen, f"runtime:{DEFAULT_RUNTIME_ID}")
            await _choose(pilot, screen, "auth_skip")

    asyncio.run(run())

    assert results == [1]
    assert load_global_config() is None


def test_a_failed_acp_probe_can_still_finish_and_records_the_failure(monkeypatch, tmp_path):
    """Continuing anyway saves the config with the probe marked as not passed."""
    _Env(monkeypatch, [[OK_CLI, LOGGED_IN]])
    monkeypatch.setattr(_Engine, "probe", {"ok": False, "message": "no", "error": "handshake"})
    results: list[int | None] = []
    screen = OnboardingScreen()

    async def run() -> None:
        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await _choose(pilot, screen, f"runtime:{DEFAULT_RUNTIME_ID}")
            await _submit(pilot, screen, str(tmp_path))
            assert _status(screen) == strings.ONBOARD_ACP_CONNECTION
            assert _report(screen) == "handshake"
            assert _option_ids(screen) == ["acp_continue", "quit"]

            await _choose(pilot, screen, "acp_continue")

    asyncio.run(run())

    assert results == [0]
    saved = load_global_config()
    assert saved is not None
    assert saved.acp_test_passed is False
    assert saved.auth_method == get_runtime(DEFAULT_RUNTIME_ID).auth_method_label


def _onboard_before(workspace: Path) -> None:
    runtime = get_runtime(DEFAULT_RUNTIME_ID)
    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=list(runtime.acp_command),
        auth_method="api_key",
        workspace_dir=workspace,
        model="Auto",
        permission_policy="ask",
        acp_test_passed=True,
        default_agent=DEFAULT_RUNTIME_ID,
    )


def test_an_existing_config_is_kept_unless_the_user_reconfigures(monkeypatch, tmp_path):
    """Re-running the wizard never overwrites silently; keeping it ends with success."""
    _Env(monkeypatch, [])
    _onboard_before(tmp_path)
    kept: list[int | None] = []
    first = OnboardingScreen()

    async def keep() -> None:
        app = _app(first, kept)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            assert _status(first) == strings.ONBOARD_CONFIG_EXISTS
            assert _option_ids(first) == ["overwrite_yes", "overwrite_no"]
            await _choose(pilot, first, "overwrite_no")

    asyncio.run(keep())
    assert kept == [0]

    env = _Env(monkeypatch, [[OK_CLI, API_KEY]])
    other = tmp_path / "other"
    other.mkdir()
    redone: list[int | None] = []
    second = OnboardingScreen()

    async def reconfigure() -> None:
        from textual.widgets import Input

        app = _app(second, redone)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            await _choose(pilot, second, "overwrite_yes")
            assert _status(second) == strings.ONBOARD_DEFAULT_AGENT
            await _choose(pilot, second, f"runtime:{DEFAULT_RUNTIME_ID}")
            field = second.query_one("#onboard-input", Input)
            assert field.value == str(tmp_path.resolve()), "prefilled with the saved workspace"
            await _submit(pilot, second, str(other))

    asyncio.run(reconfigure())

    assert redone == [0]
    assert env.checks == []
    saved = load_global_config()
    assert saved is not None
    assert saved.workspace_dir == other.resolve()


def test_force_skips_the_overwrite_question_and_escape_cancels(monkeypatch, tmp_path):
    """`pulse init --force` goes straight to the agent choice; Esc exits with 130."""
    _Env(monkeypatch, [])
    _onboard_before(tmp_path)
    results: list[int | None] = []
    screen = OnboardingScreen(force=True)

    async def run() -> None:
        app = _app(screen, results)
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            assert _status(screen) == strings.ONBOARD_DEFAULT_AGENT
            await pilot.press("escape")
            await pilot.pause()

    asyncio.run(run())

    assert results == [CANCELLED]
