from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

import pytest

import pulse.store.paths as paths


def _point_at(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(paths, "GLOBAL_DIR", tmp_path)
    monkeypatch.setattr(paths, "DAEMON_META_FILE", tmp_path / "daemon.json")
    monkeypatch.setattr(paths, "DAEMON_SOCKET", tmp_path / "daemon.sock")


def _write(tmp_path: Path, *, pid: int = 111, token: str | None = None) -> None:
    paths.write_daemon_meta(
        pid=pid,
        http_host="127.0.0.1",
        http_port=1,
        socket_path=tmp_path / "daemon.sock",
        token=token or secrets.token_urlsafe(),
    )


def test_a_daemon_never_clears_the_meta_of_another(monkeypatch, tmp_path: Path):
    """The daemon that lost the race for the port must not orphan the winner."""
    _point_at(monkeypatch, tmp_path)
    _write(tmp_path)

    paths.clear_daemon_meta(222)

    assert paths.read_daemon_meta()["pid"] == 111


def test_the_owner_clears_its_own_meta(monkeypatch, tmp_path: Path):
    _point_at(monkeypatch, tmp_path)
    _write(tmp_path)

    paths.clear_daemon_meta(111)

    assert paths.read_daemon_meta() is None


def test_the_meta_carries_the_daemon_token(monkeypatch, tmp_path: Path):
    _point_at(monkeypatch, tmp_path)
    token = secrets.token_urlsafe()
    _write(tmp_path, token=token)

    assert paths.read_daemon_meta()["token"] == token


def test_the_meta_is_readable_by_its_owner_only(monkeypatch, tmp_path: Path):
    """It holds the TCP token: whoever reads it can drive the daemon."""
    _point_at(monkeypatch, tmp_path)
    previous = os.umask(0)
    try:
        _write(tmp_path)
    finally:
        os.umask(previous)

    assert stat.S_IMODE((tmp_path / "daemon.json").stat().st_mode) == 0o600


def test_rewriting_a_world_readable_meta_makes_it_private(monkeypatch, tmp_path: Path):
    """A meta left by an older daemon was 0644; the new token must not inherit that."""
    _point_at(monkeypatch, tmp_path)
    meta = tmp_path / "daemon.json"
    meta.write_text("{}", encoding="utf-8")
    meta.chmod(0o644)

    token = secrets.token_urlsafe()
    _write(tmp_path, token=token)

    assert stat.S_IMODE(meta.stat().st_mode) == 0o600
    assert paths.read_daemon_meta()["token"] == token


def test_a_reader_opened_on_the_old_meta_never_sees_the_new_token(monkeypatch, tmp_path: Path):
    """Tightening the mode does not revoke a descriptor another user opened while it was 0644."""
    _point_at(monkeypatch, tmp_path)
    meta = tmp_path / "daemon.json"
    meta.write_text("{}", encoding="utf-8")
    meta.chmod(0o644)
    token = secrets.token_urlsafe()

    with meta.open(encoding="utf-8") as opened_before:
        _write(tmp_path, token=token)
        seen = opened_before.read()

    assert seen == "{}"
    assert paths.read_daemon_meta()["token"] == token


def test_a_failed_write_leaves_no_staged_copy_of_the_token(monkeypatch, tmp_path: Path):
    """The staged file holds the token too; a failed rename must not strand it in ~/.pulse."""
    _point_at(monkeypatch, tmp_path)

    def refuse(*_args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(paths.os, "replace", refuse)

    with pytest.raises(OSError, match="disk full"):
        _write(tmp_path)

    assert list(tmp_path.iterdir()) == []
