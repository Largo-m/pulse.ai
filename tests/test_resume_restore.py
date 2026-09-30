"""Retomar reabre a run com o passado dela, não com a tela em branco."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_workflow

from pulse.store import runs as run_store
from pulse.store.runs import DONE, RUNNING, StepRecord
from pulse.tui.hydrate import restore_run
from pulse.tui.state import CockpitState, PhaseStatus


def _run_with_history(workspace: Path) -> str:
    """Uma run com o primeiro step fechado, log, tool e duração gravados."""
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    record = run_store.create_run(
        run_id="run-1",
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[
            StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester"),
            StepRecord(step_id="build", position=2, label="Construir", agent_id="tester"),
        ],
    )
    plan = record.steps[0]
    plan.status = DONE
    plan.started_at = "2026-09-29T10:00:00+00:00"
    plan.ended_at = "2026-09-29T10:02:30+00:00"
    run_store.save_step(record.id, plan)

    run_store.record_event(
        record.id, step_id="plan", kind="Assistant", title="Plano pronto", detail="Plano pronto"
    )
    run_store.record_event(
        record.id, step_id="plan", kind="Tool", title="read README.md", detail="1..80"
    )
    return record.id


def _state() -> CockpitState:
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    state = CockpitState()
    state.configure_workflow("demo")
    return state


def test_retomar_traz_log_tool_e_duracao_dos_steps_anteriores(tmp_path: Path):
    run_id = _run_with_history(tmp_path)
    state = _state()

    restore_run(state, run_id, tmp_path)

    titles = [entry.title for entry in state.entries]
    assert "Plano pronto" in titles
    assert "read README.md" in titles, "o tool também volta, não só a fala do agente"

    plan = state.phases[0]
    assert plan.status == PhaseStatus.DONE
    assert plan.elapsed_label() != "", "o step anterior mostra quanto demorou"
    assert state.phases[1].status == PhaseStatus.PENDING


def test_a_run_ao_vivo_acrescenta_em_vez_de_reescrever_o_que_voltou(tmp_path: Path):
    """Id repetido faria o stream reescrever uma linha antiga."""
    run_id = _run_with_history(tmp_path)
    state = _state()

    restore_run(state, run_id, tmp_path)
    restored = len(state.entries)
    state.add_info("Retomando Construir")

    ids = [entry.entry_id for entry in state.entries]
    assert len(ids) == restored + 1
    assert len(set(ids)) == len(ids)


def test_step_que_a_queda_pegou_no_meio_volta_como_pendente(tmp_path: Path):
    """`running` no banco é step interrompido — nada está em curso ao reabrir."""
    run_id = _run_with_history(tmp_path)
    record = run_store.load_run(run_id)
    build = record.step("build")
    build.status = RUNNING
    build.started_at = "2026-09-29T10:02:30+00:00"
    run_store.save_step(run_id, build)

    state = _state()
    restore_run(state, run_id, tmp_path)

    assert state.phases[1].status == PhaseStatus.PENDING
    assert state.phases[1].elapsed_label() == ""


def test_run_que_nao_existe_deixa_a_tela_como_estava(tmp_path: Path):
    """Histórico é contexto, não requisito: a run nova continua podendo rodar."""
    state = _state()

    restore_run(state, "nao-existe", tmp_path)

    assert state.entries == []
    assert [phase.status for phase in state.phases] == [PhaseStatus.PENDING] * 2


def test_o_cockpit_reabre_com_o_passado_antes_de_a_run_recomecar(tmp_path: Path, monkeypatch):
    """A tela, não só o estado: é o `on_mount` do cockpit que chama o restore."""
    import asyncio

    import pytest

    pytest.importorskip("textual")

    from pulse.tui.screens.cockpit import CockpitScreen
    from pulse.tui.theme import COCKPIT_CSS

    run_id = _run_with_history(tmp_path)

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            screen = CockpitScreen(
                "demo", "fazer algo", workspace=tmp_path, resume_run_id=run_id
            )
            # A run em si não roda: o que se testa é o que a tela mostra ao abrir.
            monkeypatch.setattr(screen, "_run_workflow", lambda: None)
            app.push_screen(screen)
            await pilot.pause()

            content = str(screen.query_one("#stream-content").render())
            assert "Plano pronto" in content
            assert screen.state.phases[0].status == PhaseStatus.DONE
            assert screen.state.phases[0].elapsed_label() != ""

    asyncio.run(run())


def test_a_escolha_oferece_voltar_no_lugar_de_so_visualizar():
    """"Só visualizar" prometia uma tela; "Voltar" diz o que a tecla faz."""
    import asyncio

    import pytest

    pytest.importorskip("textual")

    from pulse.tui.screens.resume_choice import BACK, RESUME, ResumeChoiceScreen
    from pulse.tui.theme import COCKPIT_CSS

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

        chosen: list[str | None] = []
        app = Harness()
        async with app.run_test(size=(80, 24)) as pilot:
            screen = ResumeChoiceScreen(slug="demo", summary="plan · steps 1/2")
            app.push_screen(screen, callback=chosen.append)
            await pilot.pause()

            options = screen.query_one("#resume-options", OptionList)
            ids = [
                str(options.get_option_at_index(index).id)
                for index in range(options.option_count)
            ]
            assert ids == [RESUME, BACK], "refazer do zero saiu; sobrou retomar"

            screen.action_back()
            await pilot.pause()
            assert chosen == [None], "voltar não escolhe nada: quem chamou fica onde está"

    asyncio.run(run())
    from pulse.tui.screens.resume_choice import ResumeChoiceScreen as Screen

    assert not hasattr(Screen, "action_just_view"), "'Só visualizar' saiu de vez"
