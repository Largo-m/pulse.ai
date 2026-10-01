"""A branch na tela, e o worktree saindo pelo histórico."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from tests.conftest import make_workflow
from tests.test_worktree import make_repo

from pulse import vcs
from pulse.config.paths import worktrees_dir
from pulse.config.project_config import update_project_defaults
from pulse.history.catalog import HistoryCatalog
from pulse.orchestrator.engine import _prepare_workspace
from pulse.store import runs as run_store
from pulse.store.runs import DONE, StepRecord
from pulse.tui.hydrate import hydrate_history_item
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.screens.settings import SettingsScreen
from pulse.tui.state import CockpitState
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream

git_only = pytest.mark.skipif(not vcs.git_available(), reason="git não está no PATH")


def _run_in(workspace: Path, *, run_id: str = "run-1", branch: str = "", worktree: str = "") -> str:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="Adicionar login",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester")],
    )
    if branch or worktree:
        run_store.set_workspace_context(record.id, worktree_path=worktree, branch=branch)
    for step in record.steps:
        step.status = DONE
        run_store.save_step(record.id, step)
    run_store.update_run(record.id, status="completed")
    return record.id


# --------------------------------------------------------------------------
# A branch ao lado do modelo
# --------------------------------------------------------------------------


def test_meta_do_stream_mostra_modelo_e_branch():
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    state.set_model("opus")
    state.set_branch("pulse/demo-abc123")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.mount(LogStream(state, id="log-stream"))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            app.query_one(LogStream).sync_from_state(state, force=True)
            await pilot.pause()
            meta = str(app.query_one("#stream-meta").render())
            assert "opus · pulse/demo-abc123" in meta

    asyncio.run(run())


def test_sem_branch_a_meta_fica_como_era():
    """Projeto fora de git não ganha separador pendurado no modelo."""
    state = CockpitState()
    make_workflow("demo")
    state.configure_workflow("demo")
    state.set_model("opus")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.mount(LogStream(state, id="log-stream"))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            app.query_one(LogStream).sync_from_state(state, force=True)
            await pilot.pause()
            meta = str(app.query_one("#stream-meta").render())
            assert "opus" in meta
            assert "·  " not in meta.split("opus")[-1]

    asyncio.run(run())


def test_historico_reabre_com_a_branch_da_run(tmp_path: Path):
    run_id = _run_in(tmp_path, branch="pulse/demo-abc123")
    item = HistoryCatalog(tmp_path).get(run_id)
    assert item is not None
    assert item.branch == "pulse/demo-abc123"
    assert hydrate_history_item(item, tmp_path).branch_label == "pulse/demo-abc123"


def test_retomar_reabre_com_a_branch_da_run(tmp_path: Path):
    from pulse.tui.hydrate import restore_run

    run_id = _run_in(tmp_path, branch="pulse/demo-abc123")
    state = CockpitState()
    state.configure_workflow("demo")
    exec_root = restore_run(state, run_id, tmp_path)
    assert state.branch_label == "pulse/demo-abc123"
    # Sem worktree, onde a run trabalha é a própria raiz.
    assert exec_root == str(tmp_path.resolve())


def test_retomar_aponta_para_o_worktree_antes_do_motor_falar(tmp_path: Path):
    """A tela não pode ler artefato da raiz enquanto o `run.context` não chega."""
    from pulse.tui.hydrate import restore_run

    worktree = tmp_path / "wt"
    worktree.mkdir()
    run_id = _run_in(tmp_path, branch="pulse/demo-abc", worktree=str(worktree))
    state = CockpitState()
    state.configure_workflow("demo")
    assert restore_run(state, run_id, tmp_path) == str(worktree)


# --------------------------------------------------------------------------
# Remoção do worktree
# --------------------------------------------------------------------------


@git_only
def test_remover_worktree_pelo_catalogo(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    run_id = _run_in(repo)
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, _branch = _prepare_workspace(record, repo, type("R", (), {"use_worktree": True})())

    item = HistoryCatalog(repo).get(run_id)
    assert item is not None
    assert item.worktree_path == str(exec_dir)

    assert HistoryCatalog(repo).remove_worktree(item) is True
    assert not exec_dir.exists()
    # O banco esquece o caminho: oferecer remover de novo não faria sentido.
    stored = run_store.load_run(run_id)
    assert stored is not None
    assert stored.worktree_path == ""


@git_only
def test_worktree_sujo_nao_e_apagado_em_silencio(tmp_path: Path):
    """Trabalho não commitado lá dentro não é nosso para jogar fora."""
    repo = make_repo(tmp_path / "repo")
    run_id = _run_in(repo)
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, _ = _prepare_workspace(record, repo, type("R", (), {"use_worktree": True})())
    (exec_dir / "rascunho.md").write_text("não commitado\n", encoding="utf-8")

    item = HistoryCatalog(repo).get(run_id)
    assert item is not None
    assert HistoryCatalog(repo).remove_worktree(item) is False
    assert exec_dir.exists()

    # Apagar a run do histórico também respeita isso — a run sai, o diretório fica.
    assert HistoryCatalog(repo).delete(run_id) is True
    assert exec_dir.exists()
    assert run_store.load_run(run_id) is None


@git_only
def test_apagar_run_limpa_o_worktree_limpo(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    run_id = _run_in(repo)
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, _ = _prepare_workspace(record, repo, type("R", (), {"use_worktree": True})())

    assert HistoryCatalog(repo).delete(run_id) is True
    assert not exec_dir.exists()
    assert not (worktrees_dir() / run_id).exists()


@git_only
def test_detalhe_oferece_remover_so_quando_ha_worktree(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")
    plain_id = _run_in(repo, run_id="run-sem-wt")
    plain = HistoryCatalog(repo).get(plain_id)
    assert plain is not None

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryDetailScreen(plain, workspace=repo))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryDetailScreen)
            assert screen.check_action("remove_worktree", ()) is False

    asyncio.run(run())


@git_only
def test_detalhe_le_artefato_de_dentro_do_worktree(tmp_path: Path):
    """O painel procura o arquivo onde o agente escreveu, não na raiz."""
    repo = make_repo(tmp_path / "repo")
    run_id = _run_in(repo)
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, _ = _prepare_workspace(record, repo, type("R", (), {"use_worktree": True})())
    (exec_dir / "PLANO.md").write_text("# plano\n\nconteúdo do worktree\n", encoding="utf-8")
    run_store.record_artifact(run_id, "PLANO.md", step_id="plan")

    item = HistoryCatalog(repo).get(run_id)
    assert item is not None
    state = hydrate_history_item(item, repo)
    assert [artifact.path for artifact in state.artifacts] == ["PLANO.md"]
    assert state.artifacts[0].has_content is True


# --------------------------------------------------------------------------
# A chave nas configurações
# --------------------------------------------------------------------------


@git_only
def test_configuracoes_oferece_a_chave_em_repo_git(tmp_path: Path):
    repo = make_repo(tmp_path / "repo")

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(SettingsScreen(cwd=repo))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, SettingsScreen)
            options = screen.query_one("#settings-options", OptionList)
            ids = [
                options.get_option_at_index(index).id
                for index in range(options.option_count)
            ]
            assert "worktree" in ids

            screen._toggle_worktree()
            await pilot.pause()
            assert screen._worktree_enabled() is True
            screen._toggle_worktree()
            await pilot.pause()
            assert screen._worktree_enabled() is False

    asyncio.run(run())


def test_configuracoes_esconde_a_chave_fora_de_git(tmp_path: Path):
    """Chave que não liga nada é pior do que chave nenhuma."""
    plain = tmp_path / "sem-git"
    plain.mkdir()

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(SettingsScreen(cwd=plain))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            options = app.screen.query_one("#settings-options", OptionList)
            ids = [
                options.get_option_at_index(index).id
                for index in range(options.option_count)
            ]
            assert "worktree" not in ids

    asyncio.run(run())


@git_only
def test_chave_ligada_leva_a_run_para_o_worktree(tmp_path: Path):
    """Da chave ao diretório: o caminho inteiro, sem mock no meio."""
    repo = make_repo(tmp_path / "repo")
    update_project_defaults(repo, use_worktree=True)

    from pulse.config.resolved import resolve_config

    run_id = _run_in(repo)
    record = run_store.load_run(run_id)
    assert record is not None
    exec_dir, branch = _prepare_workspace(record, repo, resolve_config(repo))

    assert exec_dir == worktrees_dir() / run_id
    assert branch.startswith("pulse/demo-")
