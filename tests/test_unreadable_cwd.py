"""Pulse keeps going when the current directory is unreadable.

The detached daemon inherits its launcher's cwd. Deleting that project moves the
cwd to the Trash, where macOS denies even `getcwd()` (`EPERM`), and every new run
died in `resolve_config` with an opaque "Operation not permitted".

Two defenses, both tested: the daemon anchors itself in `~/.pulse`, and
`safe_cwd` absorbs the failure for callers that still hit it.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pulse.config.project_config import find_project_root, init_project_config
from pulse.config.resolved import resolve_config
from pulse.daemon.server import _anchor_cwd
from pulse.paths import global_state_dir, safe_cwd


@pytest.fixture
def unreadable_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """`os.getcwd()` refuses, as in a macOS-protected folder."""

    def _deny() -> str:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "getcwd", _deny)


def test_safe_cwd_returns_current_directory_when_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert safe_cwd() == Path.cwd()


def test_safe_cwd_falls_back_to_pulse_state_when_unreadable(unreadable_cwd: None) -> None:
    assert safe_cwd() == global_state_dir()


def test_resolve_config_with_workspace_does_not_depend_on_cwd(
    tmp_path: Path,
    unreadable_cwd: None,
) -> None:
    """The broken case: starting a spec with the engine in an unreadable cwd.

    The daemon always passes the workspace, so the run never needs its own cwd.
    """
    project = tmp_path / "projeto"
    project.mkdir()
    init_project_config(project)

    resolved = resolve_config(workspace=project)

    assert resolved.workspace_dir == project.resolve()


def test_resolve_config_without_workspace_does_not_raise(unreadable_cwd: None) -> None:
    """With no project to point at, the worst outcome is finding no project."""
    resolved = resolve_config()

    assert resolved.workspace_dir == global_state_dir()
    assert resolved.agent_name


def test_find_project_root_without_readable_cwd(unreadable_cwd: None) -> None:
    assert find_project_root() is None


def test_daemon_anchors_in_its_own_state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The engine leaves its launcher's directory as soon as it starts."""
    home = tmp_path / "estado"
    monkeypatch.setattr("pulse.paths.GLOBAL_DIR", home)
    origin = tmp_path / "projeto-que-vai-sumir"
    origin.mkdir()
    monkeypatch.chdir(origin)

    _anchor_cwd()

    assert Path.cwd().resolve() == home.resolve()
