"""`pulse config show|init`: what the user reads about the effective config.

The database is isolated per test (`PULSE_DB`), so every project registration
here is real SQLite and nothing leaks between tests.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from pulse.config.commands import run_config_command
from pulse.config.project_config import find_project_root


def _lines(out: str) -> list[str]:
    return [" ".join(line.split()) for line in out.splitlines()]


def test_show_outside_a_project_prints_defaults_without_a_project_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    exit_code = run_config_command(cwd=tmp_path)

    lines = _lines(capsys.readouterr().out)
    assert exit_code == 0
    assert lines[0] == "Effective config"
    assert f"workspace_dir {tmp_path.resolve()} (cwd)" in lines
    assert "worktree off (project)" in lines
    assert not any(line.startswith("project_config") for line in lines)


def test_show_for_a_workflow_names_it_in_the_title(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    run_config_command(action="show", workflow="review", cwd=tmp_path)

    assert capsys.readouterr().out.splitlines()[0] == "Effective config · workflow review"


def test_show_prints_each_value_with_its_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """The source is how a user learns which layer to edit; every row must carry one."""
    run_config_command(cwd=tmp_path)

    rows = {line.split()[0]: line for line in _lines(capsys.readouterr().out)[1:]}
    for key in ("agent", "model", "permission_policy", "workspace_dir"):
        assert rows[key].endswith(")"), rows[key]
        assert "(" in rows[key]


def test_init_registers_the_project_and_reports_its_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    exit_code = run_config_command(action="init", cwd=tmp_path)

    assert exit_code == 0
    assert capsys.readouterr().out == f"Project registered in SQLite: {tmp_path.resolve()}\n"
    assert find_project_root(tmp_path) == tmp_path.resolve()


def test_show_inside_a_registered_project_points_at_the_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    """A subdirectory resolves to its registered root, as config lookup walks parents."""
    run_config_command(action="init", cwd=tmp_path)
    capsys.readouterr()
    nested = tmp_path / "src"
    nested.mkdir()

    run_config_command(cwd=nested)

    lines = _lines(capsys.readouterr().out)
    assert f"project_config {tmp_path.resolve()}" in lines
    assert f"workspace_dir {tmp_path.resolve()} (project_root)" in lines


def test_init_twice_keeps_one_registration(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Re-running init must not fail or duplicate the project."""
    assert run_config_command(action="init", cwd=tmp_path) == 0
    assert run_config_command(action="init", cwd=tmp_path) == 0

    assert capsys.readouterr().out.count("Project registered in SQLite") == 2
    with sqlite3.connect(os.environ["PULSE_DB"]) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM projects WHERE root_path = ?", (str(tmp_path.resolve()),)
        ).fetchone()
    assert rows == (1,)


def test_without_cwd_the_current_directory_is_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.chdir(tmp_path)

    run_config_command()

    assert f"workspace_dir {tmp_path.resolve()} (cwd)" in _lines(capsys.readouterr().out)
