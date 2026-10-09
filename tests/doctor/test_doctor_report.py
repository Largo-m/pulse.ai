"""`pulse doctor --local`: what it prints and the exit code a script relies on."""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.acp.client import AcpProbeResult
from pulse.config.global_config import GlobalConfig, save_global_config
from pulse.config.project_config import update_project_defaults
from pulse.doctor import report
from pulse.doctor.checks import CheckResult


@pytest.fixture
def checks(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[CheckResult]:
    """The runtime checks the report starts from; a test edits the list to make one fail."""
    monkeypatch.chdir(tmp_path)
    found = [CheckResult(name="Runtime", status="ok", message="agent found")]
    monkeypatch.setattr(report, "run_doctor_checks", lambda _runtime: list(found))
    return found


@pytest.fixture
def probes(monkeypatch: pytest.MonkeyPatch) -> list[AcpProbeResult]:
    """Queue of probe answers; an empty queue means the probe must not run."""
    queued: list[AcpProbeResult] = []

    def probe(*, command: list[str], cwd: str) -> AcpProbeResult:
        return queued.pop(0)

    monkeypatch.setattr(report, "probe_acp_connection", probe)
    return queued


def test_a_clean_machine_reports_only_the_runtime_checks(checks, capsys):
    assert report.run_doctor() == 0
    assert capsys.readouterr().out == "✓ agent found\n"


def test_global_and_project_config_are_summarized(checks, capsys, tmp_path):
    save_global_config(
        GlobalConfig(
            version=1,
            agent_binary="agent",
            acp_command=["agent", "acp"],
            auth_method="cursor_login",
            workspace_dir=tmp_path,
            model="Auto",
            permission_policy="ask",
        )
    )
    update_project_defaults(tmp_path, model="sonnet", permission_policy="deny_writes")

    assert report.run_doctor() == 0

    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith("✓ Config in ")
    assert " — model=Auto, permissions=ask, agents=" in lines[1]
    assert lines[2] == (f"✓ Config in {tmp_path.resolve()} — model=sonnet, permissions=deny_writes")


def test_a_project_without_overrides_says_so(checks, capsys, tmp_path):
    update_project_defaults(tmp_path)

    report.run_doctor()

    assert capsys.readouterr().out.splitlines()[-1].endswith("— no overrides")


def test_the_acp_probe_is_skipped_while_a_check_fails(checks, probes, capsys):
    """Probing a runtime that is not installed would only repeat the failure."""
    checks[0] = CheckResult(name="Runtime", status="fail", message="agent missing")

    assert report.run_doctor(test_acp=True) == 1

    out = capsys.readouterr().out.splitlines()
    assert out[-1].startswith("! ACP test skipped — Fix the `")


def test_a_passing_probe_is_reported_with_its_answer(checks, probes, capsys):
    probes.append(AcpProbeResult(success=True, message="ACP ok", response_text="pong"))

    assert report.run_doctor(test_acp=True) == 0

    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["✓ ACP ok — pong", "  ACP test: ACP ok"]


def test_a_failing_probe_fails_the_doctor_with_its_error(checks, probes, capsys):
    probes.append(AcpProbeResult(success=False, message="ACP failed", error="auth required"))

    assert report.run_doctor(test_acp=True) == 1

    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == ["✗ ACP failed", "  ACP test: auth required"]
