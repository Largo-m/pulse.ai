from pulse.doctor.checks import (
    check_agent_in_path,
    check_auth,
    run_agent_checks,
    run_environment_checks,
)
from pulse.runtimes import all_runtimes, get_runtime


class Completed:
    def __init__(self, stdout: str = "", stderr: str = "") -> None:
        self.stdout = stdout
        self.stderr = stderr


def _which(monkeypatch, result):
    monkeypatch.setattr("pulse.runtimes.base.shutil.which", lambda _: result)


def _cli(monkeypatch, completed):
    monkeypatch.setattr(
        "pulse.runtimes.base.AgentRuntime.run_cli",
        lambda self, command, **kwargs: completed,
    )


def test_check_agent_in_path_missing(monkeypatch):
    _which(monkeypatch, None)
    assert check_agent_in_path().status == "fail"


def test_check_agent_in_path_found(monkeypatch):
    _which(monkeypatch, "/usr/bin/agent")
    _cli(monkeypatch, Completed(stdout="1.2.3"))
    result = check_agent_in_path()
    assert result.status == "ok"
    assert "/usr/bin/agent" in result.message


def test_check_auth_api_key(monkeypatch):
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")
    result = check_auth()
    assert result.status == "ok"
    assert result.detail == "api_key"


def test_check_auth_logged_in(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    _which(monkeypatch, "/usr/bin/agent")
    _cli(monkeypatch, Completed(stdout="✓ Logged in as user@example.com"))
    result = check_auth()
    assert result.status == "ok"
    assert result.detail == "user@example.com"


def test_check_auth_missing(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    _which(monkeypatch, "/usr/bin/agent")
    _cli(monkeypatch, Completed(stdout="Not logged in"))
    assert check_auth().status == "fail"


def test_claude_auth_reads_json_status(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _which(monkeypatch, "/usr/bin/claude")
    _cli(monkeypatch, Completed(stdout='{"loggedIn": true, "authMethod": "claude.ai"}'))
    result = check_auth("claude")
    assert result.status == "ok"
    assert result.detail == "claude.ai"


def test_claude_logged_out_is_authoritative(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _which(monkeypatch, "/usr/bin/claude")
    _cli(monkeypatch, Completed(stdout='{"loggedIn": false, "authMethod": "none"}'))
    assert check_auth("claude").status == "fail"


def test_claude_unparseable_status_warns(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _which(monkeypatch, "/usr/bin/claude")
    _cli(monkeypatch, Completed(stdout="algo inesperado"))
    assert check_auth("claude").status == "warn"


def test_claude_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    result = check_auth("claude")
    assert result.status == "ok"
    assert result.detail == "api_key"


def test_claude_checks_include_npx(monkeypatch):
    _which(monkeypatch, None)
    names = [check.name for check in run_agent_checks("claude")]
    assert "npx" in names


def test_run_agent_checks_routes_by_runtime(monkeypatch):
    _which(monkeypatch, None)
    assert run_agent_checks("cursor")[0].name == "Cursor CLI"
    assert run_agent_checks("claude")[0].name == "Claude Code CLI"
    # runtime desconhecido cai no default
    assert run_agent_checks("default")[0].name == "Cursor CLI"


def test_run_environment_checks_covers_every_runtime(monkeypatch):
    _which(monkeypatch, None)
    names = [check.name for check in run_environment_checks()]
    for runtime in all_runtimes():
        assert f"{runtime.label} CLI" in names


def test_get_runtime_falls_back_to_cursor():
    assert get_runtime("inexistente").id == "cursor"
    assert get_runtime(None).id == "cursor"
    assert get_runtime("CLAUDE").id == "claude"
