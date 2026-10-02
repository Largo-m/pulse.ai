"""Quando o diretório atual não dá para ler, o Pulse segue em frente.

O daemon vive destacado, com o cwd que herdou de quem o iniciou — e esse
diretório não é dele. Apagar o projeto de onde o engine subiu move o cwd dele
para a Lixeira, onde o macOS nega até `getcwd()` (`EPERM`). Antes disso aqui,
toda run nova morria no `resolve_config`, antes do primeiro step, com um
"Operation not permitted" que não dizia nada a ninguém.

Duas defesas, e as duas têm teste: o daemon se ancora em `~/.pulse` para nunca
chegar nesse estado, e `safe_cwd` segura o tranco de quem chegou.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pulse.config.paths import global_state_dir, safe_cwd
from pulse.config.project_config import find_project_root, init_project_config
from pulse.config.resolved import resolve_config
from pulse.daemon.server import _anchor_cwd


@pytest.fixture
def unreadable_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """`os.getcwd()` recusa, como numa pasta protegida pelo macOS."""

    def _deny() -> str:
        raise PermissionError(1, "Operation not permitted")

    monkeypatch.setattr(os, "getcwd", _deny)


def test_safe_cwd_devolve_o_diretorio_atual_quando_da(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    assert safe_cwd() == Path.cwd()


def test_safe_cwd_cai_no_estado_do_pulse_quando_nao_da(unreadable_cwd: None) -> None:
    assert safe_cwd() == global_state_dir()


def test_resolve_config_com_workspace_nao_depende_do_cwd(
    tmp_path: Path,
    unreadable_cwd: None,
) -> None:
    """O caso que quebrava: iniciar uma spec com o engine num cwd ilegível.

    O daemon sempre diz qual é o workspace — a run nunca precisou do cwd dele.
    """
    project = tmp_path / "projeto"
    project.mkdir()
    init_project_config(project)

    resolved = resolve_config(workspace=project)

    assert resolved.workspace_dir == project.resolve()


def test_resolve_config_sem_workspace_nao_levanta(unreadable_cwd: None) -> None:
    """Sem projeto para apontar, o pior desfecho é não achar projeto nenhum."""
    resolved = resolve_config()

    assert resolved.workspace_dir == global_state_dir()
    assert resolved.agent_name


def test_find_project_root_sem_cwd_legivel(unreadable_cwd: None) -> None:
    assert find_project_root() is None


def test_daemon_se_ancora_no_proprio_estado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O engine larga o diretório de quem o iniciou assim que sobe."""
    home = tmp_path / "estado"
    monkeypatch.setattr("pulse.daemon.paths.GLOBAL_DIR", home)
    origin = tmp_path / "projeto-que-vai-sumir"
    origin.mkdir()
    monkeypatch.chdir(origin)

    _anchor_cwd()

    assert Path.cwd().resolve() == home.resolve()
