from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.domain.run import StepRecord, StepStatus
from pulse.history.catalog import HistoryCatalog
from pulse.store import runs as run_store
from pulse.tui.screens.history import HistoryListScreen
from pulse.tui.screens.history_detail import HistoryDetailScreen
from pulse.tui.state import PhaseStatus
from pulse.tui.theme import COCKPIT_CSS
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSidebar
from tests.conftest import make_workflow, store_run_status, store_step


def _finished_run(workspace: Path, run_id: str, prompt: str) -> str:
    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt=prompt,
        steps=[
            StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester"),
            StepRecord(step_id="build", position=2, label="Construir", agent_id="tester"),
        ],
    )
    for step in record.steps:
        step.status = StepStatus.DONE
        store_step(record.id, step)
    store_run_status(record.id, "completed")
    return record.id


def test_history_list_filters_items(tmp_path: Path):
    _finished_run(tmp_path, "run-login", "Adicionar login social")
    _finished_run(tmp_path, "run-token", "Corrigir refresh token")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)
            assert set(screen._items) == {"run-login", "run-token"}

            screen._query = "token"
            screen._refresh()
            await pilot.pause()
            assert set(screen._items) == {"run-token"}

    asyncio.run(run())


def test_history_detail_renders_steps_without_run_log(tmp_path: Path):
    run_id = _finished_run(tmp_path, "run-login", "Adicionar login social")
    item = HistoryCatalog(tmp_path).get(run_id)
    assert item is not None

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryDetailScreen(item, workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryDetailScreen)
            assert screen.state.phases[0].status == PhaseStatus.DONE
            content = str(screen.query_one("#stream-content").render())
            phases = str(screen.query_one("#phase-content").render())
            assert "Planejar" in phases
            assert "Nenhum log persistido" in content
            assert screen.state.acp_session_id == ""
            assert screen.query_one(PhaseSidebar)
            assert screen.query_one(LogStream)

    asyncio.run(run())


def test_history_detail_replays_the_log_from_the_database(tmp_path: Path):
    """The log belongs to Pulse: a run from any runtime reopens with its stream."""
    run_id = _finished_run(tmp_path, "run-login", "Adicionar login social")
    run_store.record_event(
        run_id,
        step_id="plan",
        kind="Assistant",
        title="Plano pronto",
        detail="Plano pronto",
    )
    item = HistoryCatalog(tmp_path).get(run_id)
    assert item is not None

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryDetailScreen(item, workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            content = str(app.screen.query_one("#stream-content").render())
            assert "Plano pronto" in content

    asyncio.run(run())


def test_deleting_a_run_asks_first_and_then_removes_it(tmp_path: Path):
    """`d` opens the confirmation; confirming removes the run from the list and the database."""
    _finished_run(tmp_path, "run-login", "Adicionar login social")
    _finished_run(tmp_path, "run-token", "Corrigir refresh token")

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        from pulse.tui.screens.confirm import ConfirmScreen

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)
            options = screen.query_one("#history-options", OptionList)
            options.focus()
            options.highlighted = 0
            await pilot.pause()
            doomed = screen._highlighted()
            assert doomed is not None

            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen), "removing asks first"
            await pilot.press("enter")
            await pilot.pause()
            assert doomed.item_id in screen._items, "cancelling did not remove it"

            await pilot.press("d")
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()

            assert doomed.item_id not in screen._items
            assert run_store.load_run(doomed.item_id) is None
            assert len(screen._items) == 1

    asyncio.run(run())


def test_delete_is_offered_only_when_there_is_a_run_under_the_cursor(tmp_path: Path):
    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)
            assert screen._highlighted() is None
            assert screen.check_action("delete_run", ()) is False

    asyncio.run(run())


def test_the_history_only_removes_runs_from_its_own_workspace(tmp_path: Path):
    """Same rule as `get`: history only touches what it shows."""
    other = tmp_path / "outro"
    other.mkdir()
    run_id = _finished_run(other, "run-de-fora", "Mexer em outro repo")

    assert HistoryCatalog(tmp_path).delete(run_id) is False
    assert run_store.load_run(run_id) is not None
    assert HistoryCatalog(other).delete(run_id) is True
    assert run_store.load_run(run_id) is None


def test_a_run_waiting_for_the_user_is_listed_as_live(tmp_path: Path):
    """`precisa de você` is a live run: it goes to the top and opens live.

    Otherwise it would sink among past runs with the wrong label, and opening it
    from history would show the static page, where nothing can be answered.
    """
    from pulse.history.models import LIVE_STATUSES, HistoryStatus

    _finished_run(tmp_path, "run-velha", "Já acabou")
    _finished_run(tmp_path, "run-espera", "Esperando resposta")
    store_run_status("run-espera", "awaiting_input")

    items = HistoryCatalog(tmp_path).list_items()

    assert items[0].run_id == "run-espera"
    assert items[0].status is HistoryStatus.AWAITING_INPUT
    assert items[0].status in LIVE_STATUSES
    assert items[0].status_label == "precisa de você"
    assert [item.run_id for item in HistoryCatalog(tmp_path).search("precisa")] == ["run-espera"]


def test_removing_a_live_run_warns_without_blocking(tmp_path: Path):
    """A run stuck as `executando` must be removable, but with a warning."""
    from pulse.tui.screens.history import _delete_warning

    _finished_run(tmp_path, "run-viva", "Rodando agora")
    store_run_status("run-viva", "running")
    item = HistoryCatalog(tmp_path).get("run-viva")
    assert item is not None

    warning = _delete_warning(item)

    assert "em andamento" in warning
    assert "Os arquivos no workspace ficam." in warning


def test_a_failed_run_still_offers_to_resume(tmp_path: Path):
    """Failed is not finished: the remaining steps are what can be resumed.

    History only looked at the run status, so a run that crashed midway came
    back with neither resume nor restart, and the missing tasks seemed to never
    have existed.
    """
    from pulse.tui.screens.history_detail import _pending_run

    make_workflow("demo", steps=[("plan", "Planejar"), ("build", "Construir")])
    record = run_store.create_run(
        run_id="run-broke",
        workflow_id="demo",
        workspace=tmp_path,
        user_prompt="Subir a API",
        steps=[
            StepRecord(step_id="plan", position=1, label="Planejar", agent_id="tester"),
            StepRecord(step_id="build", position=2, label="Construir", agent_id="tester"),
        ],
    )
    plan = record.steps[0]
    plan.status = StepStatus.DONE
    store_step(record.id, plan)
    store_run_status(record.id, "failed")

    item = HistoryCatalog(tmp_path).get(record.id)
    assert item is not None
    assert item.status_label == "falhou"
    assert item.is_incomplete
    assert _pending_run(item) == (record.id, "Construir · steps 1/2")


def test_history_list_follows_status_changes_without_reopening(tmp_path: Path, monkeypatch):
    """The daemon changes the run status; the list follows without leaving and returning."""
    import pulse.tui.screens.history as history_module

    monkeypatch.setattr(history_module, "REFRESH_SECONDS", 0.05)
    _finished_run(tmp_path, "run-old", "Primeira")
    _finished_run(tmp_path, "run-live", "Segunda")
    store_run_status("run-live", "running")

    async def run() -> None:
        from textual.app import App
        from textual.widgets import OptionList

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)
            options = screen.query_one("#history-options", OptionList)
            ids = [options.get_option_at_index(i).id for i in range(options.option_count)]
            options.highlighted = ids.index("run-old")
            before = screen._items["run-live"].status

            store_run_status("run-live", "completed")
            for _ in range(40):
                await pilot.pause(0.05)
                if screen._items["run-live"].status != before:
                    break

            assert screen._items["run-live"].status != before
            assert options.get_option_at_index(options.highlighted).id == "run-old"

    asyncio.run(run())


def test_a_locked_database_skips_the_poll_and_keeps_the_list(tmp_path: Path, monkeypatch):
    """The background poll must survive a busy SQLite in the daemon (a 500): the
    list stays as it was and the next poll retries, instead of the worker erroring the app."""
    import sqlite3

    _finished_run(tmp_path, "run-login", "Adicionar login social")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)

            def _locked(*_args: object) -> list:
                raise sqlite3.OperationalError("database is locked")

            monkeypatch.setattr("pulse.history.catalog.HistoryCatalog.list_items", _locked)
            screen._fetch()
            await pilot.pause()

            assert set(screen._items) == {"run-login"}

    asyncio.run(run())


def test_a_poll_answered_after_the_app_exited_is_dropped(tmp_path: Path, monkeypatch):
    """When the app can no longer take the result (`call_from_thread` raises
    `RuntimeError`), the poll ends quietly."""
    _finished_run(tmp_path, "run-login", "Adicionar login social")

    async def run() -> None:
        from textual.app import App

        class Harness(App[None]):
            CSS = COCKPIT_CSS

            def on_mount(self) -> None:
                self.push_screen(HistoryListScreen(workspace=tmp_path))

        app = Harness()
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, HistoryListScreen)

            def _app_gone(*_args) -> None:
                raise RuntimeError("App is not running")

            monkeypatch.setattr(app, "call_from_thread", _app_gone)
            screen._fetch()

            assert set(screen._items) == {"run-login"}

    asyncio.run(run())


def test_an_unmounted_history_list_has_no_highlighted_run(tmp_path: Path):
    """Actions fired before the list is composed act on nothing rather than crash."""
    assert HistoryListScreen(workspace=tmp_path)._highlighted() is None
