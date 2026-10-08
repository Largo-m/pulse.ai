from __future__ import annotations

from pathlib import Path

import pulse.paths as paths
from pulse.cli_daemon import run_daemon_command


def test_status_reports_a_stopped_daemon(monkeypatch, tmp_path: Path, capsys):
    """`pulse daemon status` is how a user checks the engine; it must answer, not crash."""
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")

    exit_code = run_daemon_command("status")

    assert exit_code == 1
    assert capsys.readouterr().out == "pulse-engine: stopped\n"
