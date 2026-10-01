"""Worktree por run: o git que o Pulse fala, e onde a run decide trabalhar."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pulse import vcs
from pulse.config.paths import worktrees_dir
from pulse.config.project_config import init_project_config, update_project_defaults
from pulse.config.resolved import resolve_config
from pulse.orchestrator.engine import _branch_name, _prepare_workspace
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord

pytestmark = pytest.mark.skipif(not vcs.git_available(), reason="git não está no PATH")


def make_repo(path: Path) -> Path:
    """Repositório com um commit — `worktree add` precisa de um HEAD de verdade."""
    path.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=path, check=True, capture_output=True, text=True
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "pulse@example.com")
    run("config", "user.name", "Pulse")
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    run("add", "README.md")
    run("commit", "-q", "-m", "inicial")
    return path


def make_run(workspace: Path, *, run_id: str = "run-1") -> run_store.RunRecord:
    return run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="tarefa",
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
    )


class Resolved:
    """O mínimo que `_prepare_workspace` lê de uma config resolvida."""

    def __init__(self, use_worktree: bool) -> None:
        self.use_worktree = use_worktree


# --------------------------------------------------------------------------
# pulse.vcs
# --------------------------------------------------------------------------


def test_repo_root_and_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    assert vcs.repo_root(repo) == repo.resolve()
    assert vcs.current_branch(repo) == "main"


def test_fora_de_repositorio_nao_levanta(tmp_path: Path) -> None:
    plain = tmp_path / "sem-git"
    plain.mkdir()
    assert vcs.repo_root(plain) is None
    assert vcs.current_branch(plain) == ""
    assert vcs.is_repo(plain) is False


def test_caminho_inexistente_nao_levanta(tmp_path: Path) -> None:
    missing = tmp_path / "nao-existe"
    assert vcs.repo_root(missing) is None
    assert vcs.current_branch(missing) == ""


def test_add_worktree_cria_branch_e_diretorio(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    branch = vcs.add_worktree(repo, target, "pulse/demo-abc")
    assert branch == "pulse/demo-abc"
    assert (target / "README.md").exists()
    assert vcs.current_branch(target) == "pulse/demo-abc"
    # A árvore de trabalho original não foi tocada.
    assert vcs.current_branch(repo) == "main"


def test_branch_existente_ganha_sufixo(tmp_path: Path) -> None:
    """Worktree removido deixa a branch para trás; o nome seguinte desvia dela.

    Reaproveitar a branch faria duas runs escreverem no mesmo histórico.
    """
    repo = make_repo(tmp_path / "repo")
    first = vcs.add_worktree(repo, tmp_path / "wt1", "pulse/demo-abc")
    second = vcs.add_worktree(repo, tmp_path / "wt2", "pulse/demo-abc")
    assert first == "pulse/demo-abc"
    assert second == "pulse/demo-abc-2"


def test_remove_worktree_recusa_diretorio_sujo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    vcs.add_worktree(repo, target, "pulse/demo-abc")
    (target / "novo.txt").write_text("trabalho não salvo\n", encoding="utf-8")

    assert vcs.has_changes(target) is True
    with pytest.raises(vcs.GitError):
        vcs.remove_worktree(repo, target)
    assert target.exists()

    vcs.remove_worktree(repo, target, force=True)
    assert not target.exists()


def test_remove_worktree_limpo(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    vcs.add_worktree(repo, target, "pulse/demo-abc")
    assert vcs.has_changes(target) is False
    vcs.remove_worktree(repo, target)
    assert not target.exists()


# --------------------------------------------------------------------------
# _prepare_workspace
# --------------------------------------------------------------------------


def test_sem_isolamento_roda_na_raiz_e_grava_a_branch(tmp_path: Path) -> None:
    """Chave desligada: nada de worktree, mas a branch aparece mesmo assim."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)

    exec_dir, branch = _prepare_workspace(run, repo, Resolved(use_worktree=False))

    assert exec_dir == repo
    assert branch == "main"
    stored = run_store.load_run(run.id)
    assert stored is not None
    assert stored.worktree_path == ""
    assert stored.branch == "main"


def test_projeto_fora_de_git_nao_isola(tmp_path: Path) -> None:
    """Chave ligada sem repositório não pode impedir a run de rodar."""
    plain = tmp_path / "sem-git"
    plain.mkdir()
    run = make_run(plain)

    exec_dir, branch = _prepare_workspace(run, plain, Resolved(use_worktree=True))

    assert exec_dir == plain
    assert branch == ""


def test_isolamento_abre_worktree_e_grava_no_banco(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)

    exec_dir, branch = _prepare_workspace(run, repo, Resolved(use_worktree=True))

    assert exec_dir == worktrees_dir() / run.id
    assert exec_dir.is_dir()
    assert branch == _branch_name(run)
    assert vcs.current_branch(exec_dir) == branch
    # A raiz do projeto continua intocada — é o ponto do isolamento.
    assert vcs.current_branch(repo) == "main"

    stored = run_store.load_run(run.id)
    assert stored is not None
    assert stored.worktree_path == str(exec_dir)
    assert stored.branch == branch
    # A identidade da run continua sendo o projeto, senão o histórico a perde.
    assert stored.workspace_root == str(repo.resolve())
    assert stored.exec_root == str(exec_dir)


def test_retomar_reusa_o_worktree_da_run(tmp_path: Path) -> None:
    """Abrir um segundo worktree jogaria fora o que os steps já fecharam."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, branch = _prepare_workspace(run, repo, Resolved(use_worktree=True))
    (first / "entrega.md").write_text("trabalho do step 1\n", encoding="utf-8")

    retomada = run_store.load_run(run.id)
    assert retomada is not None
    second, same_branch = _prepare_workspace(retomada, repo, Resolved(use_worktree=True))

    assert second == first
    assert same_branch == branch
    assert (second / "entrega.md").exists()


def test_worktree_sumiu_do_disco_abre_outro(tmp_path: Path) -> None:
    """Diretório apagado à mão não pode travar a retomada da run."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, _ = _prepare_workspace(run, repo, Resolved(use_worktree=True))
    vcs.remove_worktree(repo, first, force=True)

    retomada = run_store.load_run(run.id)
    assert retomada is not None
    second, branch = _prepare_workspace(retomada, repo, Resolved(use_worktree=True))

    assert second.is_dir()
    # Branch nova: a anterior ficou para trás com o worktree removido.
    assert branch == f"{_branch_name(run)}-2"


def test_runs_simultaneas_nao_dividem_diretorio(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    one, _ = _prepare_workspace(make_run(repo, run_id="run-a"), repo, Resolved(True))
    two, _ = _prepare_workspace(make_run(repo, run_id="run-b"), repo, Resolved(True))
    assert one != two
    assert one.is_dir() and two.is_dir()


def test_branch_name_higieniza_o_workflow(tmp_path: Path) -> None:
    run = run_store.RunRecord(
        id="0123456789abcdef",
        workflow_id="nova spec/v2",
        workspace_root=str(tmp_path),
    )
    assert _branch_name(run) == "pulse/nova-spec-v2-01234567"


# --------------------------------------------------------------------------
# Config do projeto
# --------------------------------------------------------------------------


def test_chave_do_projeto_chega_na_config_resolvida(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    init_project_config(repo)
    assert resolve_config(repo).use_worktree is False

    update_project_defaults(repo, use_worktree=True)
    assert resolve_config(repo).use_worktree is True

    update_project_defaults(repo, use_worktree=False)
    assert resolve_config(repo).use_worktree is False


def test_chave_sobrevive_a_outras_edicoes_do_projeto(tmp_path: Path) -> None:
    """Gravar modelo não pode desligar o isolamento de quem já o ligou."""
    repo = make_repo(tmp_path / "repo")
    update_project_defaults(repo, use_worktree=True)
    update_project_defaults(repo, model="sonnet")
    assert resolve_config(repo).use_worktree is True
