from __future__ import annotations

from pathlib import Path

import pulse.daemon.paths as paths


def _point_at(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "GLOBAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")
    monkeypatch.setattr(paths, "DAEMON_PID_FILE", tmp_path / "daemon.pid")
    monkeypatch.setattr(paths, "DAEMON_SOCKET", tmp_path / "daemon.sock")


def test_a_daemon_never_clears_the_meta_of_another(monkeypatch, tmp_path: Path):
    """Quem perdeu a corrida pela porta não pode deixar o vencedor órfão."""
    _point_at(monkeypatch, tmp_path)
    paths.write_daemon_meta(pid=111, http_host="127.0.0.1", http_port=1, socket_path=tmp_path / "daemon.sock")

    paths.clear_daemon_meta(222)

    assert paths.read_daemon_meta()["pid"] == 111


def test_the_owner_clears_its_own_meta(monkeypatch, tmp_path: Path):
    _point_at(monkeypatch, tmp_path)
    paths.write_daemon_meta(pid=111, http_host="127.0.0.1", http_port=1, socket_path=tmp_path / "daemon.sock")

    paths.clear_daemon_meta(111)

    assert paths.read_daemon_meta() is None
