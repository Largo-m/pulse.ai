from __future__ import annotations

import os
from pathlib import Path

import pulse.cli_daemon as cli_daemon
import pulse.client.daemon_process as daemon_process
import pulse.paths as paths
from pulse.cli_daemon import run_daemon_command


def test_status_reports_a_stopped_daemon(monkeypatch, tmp_path: Path, capsys):
    """`pulse daemon status` is how a user checks the engine; it must answer, not crash."""
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")

    exit_code = run_daemon_command("status")

    assert exit_code == 1
    assert capsys.readouterr().out == "pulse-engine: stopped\n"


def test_status_reports_a_live_daemon_with_its_endpoints(monkeypatch, tmp_path: Path, capsys):
    """A live engine must show where to reach it; the meta file is the only source for that."""
    socket_path = tmp_path / "daemon.sock"
    socket_path.touch()
    monkeypatch.setattr(paths, "GLOBAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")
    monkeypatch.setattr(daemon_process, "DAEMON_SOCKET", socket_path)
    # The fake socket file accepts no connections; stub the run listing at the HTTP boundary.
    monkeypatch.setattr(cli_daemon, "active_runs", lambda: [])
    paths.write_daemon_meta(
        pid=os.getpid(), http_host="127.0.0.1", http_port=9911, socket_path=socket_path
    )

    exit_code = run_daemon_command("status")

    assert exit_code == 0
    assert capsys.readouterr().out == (
        "pulse-engine: running\n"
        f"  pid: {os.getpid()}\n"
        f"  socket: {socket_path}\n"
        "  http: 127.0.0.1:9911\n"
    )
