from __future__ import annotations

from pathlib import Path

from pulse.history.models import HistoryItem, HistoryKind, HistoryStatus, SpecFlow
from pulse.plan.new_issue_flow import _apply_spec_decision
from pulse.plan.workflow_state import (
    PhaseStatus,
    WorkflowState,
    find_workflow_by_slug,
    workflow_is_incomplete,
)
from pulse.tui.screens.history_detail import _pending_workflow


def _item(slug: str, flow: SpecFlow = SpecFlow.FULL) -> HistoryItem:
    folder = "features" if flow == SpecFlow.FULL else "quick"
    return HistoryItem(
        kind=HistoryKind.SPEC,
        slug=slug,
        title=slug,
        prompt="construa algo",
        status=HistoryStatus.IN_PROGRESS,
        updated_at="2026-09-24",
        spec_dir=f".pulse/specs/{folder}/{slug}",
        flow=flow,
    )


def _save_workflow(workspace: Path, slug: str) -> WorkflowState:
    state = WorkflowState.create_new(feature_slug=slug, user_prompt="construa algo")
    state.save(workspace)
    return state


def test_offers_choice_when_workflow_is_incomplete(tmp_path: Path):
    _save_workflow(tmp_path, "demo")

    pending = _pending_workflow(_item("demo"), tmp_path)

    assert pending is not None
    slug, summary = pending
    assert slug == "demo"
    assert "prd" in summary


def test_no_choice_when_everything_is_done(tmp_path: Path):
    state = _save_workflow(tmp_path, "demo")
    for phase in state.phases.values():
        phase.status = PhaseStatus.DONE
    state.save(tmp_path)

    assert _pending_workflow(_item("demo"), tmp_path) is None


def test_no_choice_without_a_workflow_file(tmp_path: Path):
    assert _pending_workflow(_item("inexistente"), tmp_path) is None


def test_quick_specs_are_not_resumable(tmp_path: Path):
    _save_workflow(tmp_path, "demo")

    assert _pending_workflow(_item("demo", flow=SpecFlow.QUICK), tmp_path) is None


def test_resume_returns_the_existing_state(tmp_path: Path):
    state = _save_workflow(tmp_path, "demo")
    state.mark_phase_done("prd")
    state.mark_phase_in_progress("techspec")
    state.save(tmp_path)

    resumed = _apply_spec_decision(tmp_path, "", "demo", "resume")

    assert resumed is not None
    assert resumed.current_phase == "techspec"
    assert resumed.phases["prd"].status == PhaseStatus.DONE


def test_restart_resets_the_phases_without_deleting_artifacts(tmp_path: Path):
    state = _save_workflow(tmp_path, "demo")
    state.mark_phase_done("prd")
    state.mark_phase_in_progress("techspec")
    state.save(tmp_path)
    artifact = tmp_path / state.feature_dir / "PRD.md"
    artifact.write_text("# spec antiga", encoding="utf-8")

    restarted = _apply_spec_decision(tmp_path, "", "demo", "restart")

    assert restarted is not None
    assert restarted.feature_slug == "demo"
    assert restarted.current_phase == "prd"
    assert restarted.phases["prd"].status == PhaseStatus.PENDING
    # refazer não apaga o que já existe: o pipeline reescreve por cima
    assert artifact.read_text(encoding="utf-8") == "# spec antiga"
    # e o estado em disco reflete o reset
    assert find_workflow_by_slug(tmp_path, "demo").current_phase == "prd"


def test_restart_keeps_the_original_prompt_when_none_is_given(tmp_path: Path):
    _save_workflow(tmp_path, "demo")

    restarted = _apply_spec_decision(tmp_path, "", "demo", "restart")

    assert restarted is not None
    assert restarted.user_prompt == "construa algo"


def test_resume_is_none_for_an_unknown_slug(tmp_path: Path):
    assert _apply_spec_decision(tmp_path, "x", "nao-existe", "resume") is None


def test_unknown_mode_is_ignored(tmp_path: Path):
    _save_workflow(tmp_path, "demo")

    assert _apply_spec_decision(tmp_path, "x", "demo", "sei-la") is None


def test_incomplete_detection_follows_pending_tasks(tmp_path: Path):
    state = _save_workflow(tmp_path, "demo")
    for phase in state.phases.values():
        phase.status = PhaseStatus.DONE
    state.save(tmp_path)
    assert workflow_is_incomplete(state) is False


def test_resume_screen_returns_the_chosen_mode():
    """A tela sobe de verdade e devolve a escolha (smoke na TUI)."""
    import asyncio

    from textual.app import App
    from textual.widgets import OptionList

    from pulse.tui.screens.resume_choice import RESTART, RESUME, ResumeChoiceScreen
    from pulse.tui.theme import COCKPIT_CSS

    class Harness(App[None]):
        CSS = COCKPIT_CSS

    async def pick(option_id: str) -> str | None:
        result: list[str | None] = []
        app = Harness()
        async with app.run_test() as pilot:
            app.push_screen(
                ResumeChoiceScreen(slug="demo", summary="techspec (in_progress)"),
                callback=result.append,
            )
            await pilot.pause()
            options = app.screen.query_one("#resume-options", OptionList)
            index = next(
                i for i, opt in enumerate(options._options) if opt.id == option_id
            )
            options.highlighted = index
            await pilot.press("enter")
            await pilot.pause()
        return result[0] if result else None

    assert asyncio.run(pick(RESUME)) == "resume"
    assert asyncio.run(pick(RESTART)) == "restart"
    assert asyncio.run(pick("view")) is None


def test_opening_an_unfinished_spec_from_history_offers_the_choice(tmp_path: Path):
    """Abrir a spec pelo histórico sobe a escolha retomar/refazer."""
    import asyncio

    from textual.app import App

    from pulse.tui.screens.history_detail import HistoryDetailScreen
    from pulse.tui.screens.resume_choice import ResumeChoiceScreen
    from pulse.tui.theme import COCKPIT_CSS

    _save_workflow(tmp_path, "demo")

    class Harness(App[None]):
        CSS = COCKPIT_CSS

    async def open_detail(item: HistoryItem) -> str:
        app = Harness()
        async with app.run_test() as pilot:
            app.push_screen(HistoryDetailScreen(item, workspace=tmp_path))
            await pilot.pause()
            await pilot.pause()
            return type(app.screen).__name__

    assert open_detail.__name__  # guarda contra typo no nome
    assert asyncio.run(open_detail(_item("demo"))) == ResumeChoiceScreen.__name__


def test_opening_a_finished_spec_goes_straight_to_the_detail(tmp_path: Path):
    import asyncio

    from textual.app import App

    from pulse.tui.screens.history_detail import HistoryDetailScreen
    from pulse.tui.theme import COCKPIT_CSS

    state = _save_workflow(tmp_path, "demo")
    for phase in state.phases.values():
        phase.status = PhaseStatus.DONE
    state.save(tmp_path)

    class Harness(App[None]):
        CSS = COCKPIT_CSS

    async def open_detail() -> str:
        app = Harness()
        async with app.run_test() as pilot:
            app.push_screen(HistoryDetailScreen(_item("demo"), workspace=tmp_path))
            await pilot.pause()
            await pilot.pause()
            return type(app.screen).__name__

    assert asyncio.run(open_detail()) == HistoryDetailScreen.__name__
