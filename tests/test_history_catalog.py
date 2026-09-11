from __future__ import annotations

from pathlib import Path

from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryKind, HistoryStatus
from pulse.plan.specify_state import WorkflowState


def _write_issue(workspace: Path, slug: str, prompt: str, *, complete: bool) -> None:
    state = WorkflowState.create_new(feature_slug=slug, user_prompt=prompt)
    if complete:
        for phase in ("specify", "design", "tasks"):
            state.approve_phase(phase)
            state.mark_phase_done(phase)
        state.mark_phase_done("execute")
    else:
        state.mark_phase_in_progress("specify")
        state.mark_phase_awaiting_approval("specify")
    state.save(workspace)
    spec = workspace / ".pulse/specs/features" / slug / "spec.md"
    spec.write_text("# Spec\n", encoding="utf-8")


def _write_quick(workspace: Path, slug: str, title: str, status: str) -> None:
    path = workspace / ".pulse/specs/quick" / slug / "TASK.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Quick Task 001: {title}\n\n**Date:** 2026-01-02\n**Status:** {status}\n",
        encoding="utf-8",
    )


def test_catalog_indexes_issues_and_fixes(tmp_path: Path):
    _write_issue(tmp_path, "login-flow", "Adicionar login social", complete=True)
    _write_issue(tmp_path, "billing", "Cobrança recorrente", complete=False)
    _write_quick(tmp_path, "001-token-refresh", "Corrigir refresh token", "Done")
    _write_quick(tmp_path, "002-button", "Ajustar botão", "Awaiting Approval")

    catalog = HistoryCatalog(tmp_path)
    items = catalog.list_items()
    assert {item.slug for item in items} == {
        "login-flow",
        "billing",
        "001-token-refresh",
        "002-button",
    }
    by_slug = {item.slug: item for item in items}
    assert by_slug["login-flow"].kind == HistoryKind.ISSUE
    assert by_slug["login-flow"].status == HistoryStatus.DONE
    assert by_slug["login-flow"].run_id is None
    assert [step.id for step in by_slug["login-flow"].steps] == [
        "specify",
        "design",
        "tasks",
        "execute",
    ]
    assert by_slug["billing"].status == HistoryStatus.AWAITING_APPROVAL
    assert by_slug["001-token-refresh"].kind == HistoryKind.FIX
    assert by_slug["001-token-refresh"].status == HistoryStatus.DONE
    assert by_slug["001-token-refresh"].title == "Corrigir refresh token"
    assert by_slug["002-button"].status == HistoryStatus.AWAITING_APPROVAL
    assert [step.status for step in by_slug["001-token-refresh"].steps] == ["done", "done"]


def test_catalog_search_filters_by_text_kind_and_status(tmp_path: Path):
    _write_issue(tmp_path, "login-flow", "Adicionar login social", complete=True)
    _write_quick(tmp_path, "001-token-refresh", "Corrigir refresh token", "Done")
    _write_quick(tmp_path, "002-button", "Ajustar botão", "In Progress")

    catalog = HistoryCatalog(tmp_path)
    token = catalog.search("token")
    assert [item.slug for item in token] == ["001-token-refresh"]

    issues = catalog.search("", kind=HistoryKind.ISSUE)
    assert [item.slug for item in issues] == ["login-flow"]

    done = catalog.search("done")
    assert {item.slug for item in done} == {"login-flow", "001-token-refresh"}

    fixes = catalog.search("botão", kind=HistoryKind.FIX)
    assert [item.slug for item in fixes] == ["002-button"]
    assert fixes[0].status == HistoryStatus.IN_PROGRESS
