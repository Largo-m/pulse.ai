from unittest.mock import patch

from pulse.doctor.checks import check_agent_in_path, check_auth


def test_check_agent_in_path_missing(monkeypatch):
    monkeypatch.setattr("pulse.doctor.checks.shutil.which", lambda _: None)
    result = check_agent_in_path()
    assert result.status == "fail"


def test_check_agent_in_path_found(monkeypatch):
    monkeypatch.setattr("pulse.doctor.checks.shutil.which", lambda _: "/usr/bin/agent")

    class Completed:
        stdout = "1.2.3"
        stderr = ""

    monkeypatch.setattr("pulse.doctor.checks.subprocess.run", lambda *args, **kwargs: Completed())
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
    monkeypatch.setattr("pulse.doctor.checks.find_agent_binary", lambda: "/usr/bin/agent")

    class Completed:
        stdout = "✓ Logged in as user@example.com"
        stderr = ""

    monkeypatch.setattr("pulse.doctor.checks.subprocess.run", lambda *args, **kwargs: Completed())
    result = check_auth()
    assert result.status == "ok"


def test_check_auth_missing(monkeypatch):
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    monkeypatch.setattr("pulse.doctor.checks.find_agent_binary", lambda: "/usr/bin/agent")

    class Completed:
        stdout = "Not logged in"
        stderr = ""

    monkeypatch.setattr("pulse.doctor.checks.subprocess.run", lambda *args, **kwargs: Completed())
    result = check_auth()
    assert result.status == "fail"
