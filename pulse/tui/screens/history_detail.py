from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from pulse import vcs
from pulse.history.catalog import HistoryCatalog
from pulse.history.models import HistoryItem
from pulse.tui.hydrate import hydrate_history_item
from pulse.tui.screens.confirm import ConfirmScreen
from pulse.tui.screens.resume_choice import RESUME, ResumeChoiceScreen
from pulse.tui.widgets.app_footer import AppFooter
from pulse.tui.widgets.app_header import AppHeader
from pulse.tui.widgets.artifact_pane import (
    ArtifactPane,
    ArtifactPaneClosed,
    ArtifactPaneOpened,
    ArtifactTabSelected,
)
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import NavSelected, PhaseSidebar


class HistoryDetailScreen(Screen[None]):
    BINDINGS = [
        Binding("q", "back_list", "Voltar"),
        Binding("r", "resume_workflow", "Retomar"),
        Binding("w", "remove_worktree", "Remover worktree"),
        Binding("b", "back_list", "Voltar"),
        Binding("tab", "toggle_focus", "Focus"),
        Binding("a", "toggle_artifact_pane", "Artifacts"),
        Binding("escape", "escape_back", "Back"),
        Binding("left_square_bracket", "artifact_prev", "Prev file"),
        Binding("right_square_bracket", "artifact_next", "Next file"),
        Binding("left", "artifact_left", "Prev file"),
        Binding("right", "artifact_right", "Next file"),
        Binding("up", "nav_up", "Up", priority=True),
        Binding("down", "nav_down", "Down", priority=True),
        Binding("k", "nav_up", "Up", priority=True),
        Binding("j", "nav_down", "Down", priority=True),
    ]

    def __init__(self, item: HistoryItem, workspace: Path | None = None) -> None:
        super().__init__()
        self.item = item
        #: A raiz do projeto — é por ela que o histórico acha a run.
        self._workspace = Path(workspace or Path.cwd())
        # Onde esta run trabalhou, que pode não ser a raiz do projeto: o painel
        # de artefatos lê arquivo do disco, e o worktree é onde eles estão.
        self._cwd = item.worktree_path or str(self._workspace)
        self.state = hydrate_history_item(item, Path(self._cwd))
        self._pending = _pending_run(item)

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="cockpit-body"):
            yield PhaseSidebar(self.state, id="phase-sidebar")
            yield LogStream(self.state, id="log-stream")
            yield ArtifactPane(self.state, cwd=self._cwd, id="artifact-pane")
        yield AppFooter(back_label="VOLTAR")

    def on_mount(self) -> None:
        self._sync_ui(force=True)
        if self._pending is not None:
            self.action_resume_workflow()

    def action_resume_workflow(self) -> None:
        if self._pending is None:
            return
        run_id, summary = self._pending

        def _chosen(mode: str | None) -> None:
            if mode != RESUME:
                return
            self.app.open_cockpit(
                self.item.workflow_id,
                self.item.prompt,
                resume_run_id=run_id,
            )

        self.app.push_screen(
            ResumeChoiceScreen(slug=self.item.title, summary=summary),
            callback=_chosen,
        )

    def action_remove_worktree(self) -> None:
        """Desfaz o worktree desta run, depois de confirmar.

        A remoção é manual porque o worktree **é** a entrega: ele guarda o que
        o agente escreveu, na branch onde escreveu. Quem decide que já tirou o
        que queria de lá é quem revisou.
        """
        path = self.item.worktree_path
        if not path or not Path(path).exists():
            return
        dirty = vcs.has_changes(path)
        detail = [path, f"Branch: {self.item.branch or '—'}"]
        if dirty:
            detail.append(
                "Há mudança não commitada aqui. O git vai recusar a remoção — "
                "commite ou descarte antes."
            )
        else:
            detail.append("A branch continua no repositório; só o diretório sai.")

        def _answered(confirmed: bool | None) -> None:
            if not confirmed:
                return
            catalog = HistoryCatalog(self._workspace)
            if catalog.remove_worktree(self.item):
                self.notify("Worktree removido")
            else:
                self.notify("Worktree mantido — o git recusou a remoção")

        self.app.push_screen(
            ConfirmScreen(
                title="REMOVER WORKTREE",
                detail="\n".join(detail),
                confirm_label="Remover",
            ),
            callback=_answered,
        )

    def _sync_ui(self, *, force: bool = False) -> None:
        body = self.query_one("#cockpit-body")
        body.set_class(self.state.artifact_pane_open, "artifacts-open")
        body.set_class(
            self.state.phase_has_artifacts() and not self.state.artifact_pane_open,
            "artifacts-rail",
        )
        self.query_one(AppHeader).sync_from_state(self.state)
        self.query_one(PhaseSidebar).sync_from_state(self.state)
        self.query_one(LogStream).sync_from_state(self.state, force=force)
        self.query_one(ArtifactPane).sync_from_state(self.state, force=force)
        self.query_one(AppFooter).sync_from_state(self.state)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "resume_workflow":
            return self._pending is not None
        if action == "remove_worktree":
            return bool(self.item.worktree_path) and Path(self.item.worktree_path).exists()
        if action == "close_artifact_pane":
            return self.state.artifact_pane_open
        if action == "toggle_artifact_pane":
            return self.state.artifact_pane_open or self.state.phase_has_artifacts()
        if action in {"artifact_prev", "artifact_next"}:
            return self.state.artifact_pane_open
        if action in {"artifact_left", "artifact_right"}:
            return self.state.artifact_pane_open and self.state.focus_target == "artifact"
        return True

    def action_escape_back(self) -> None:
        if self.state.artifact_pane_open:
            self.action_close_artifact_pane()
            return
        self.action_back_list()

    def _apply_focus(self) -> None:
        if self.state.focus_target == "phases":
            self.query_one(PhaseSidebar).focus()
        elif self.state.focus_target == "artifact" and self.state.artifact_pane_open:
            self.query_one(ArtifactPane).focus()
        else:
            self.query_one(LogStream).focus()

    def action_toggle_focus(self) -> None:
        self.state.toggle_focus()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_toggle_artifact_pane(self) -> None:
        self.state.toggle_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_close_artifact_pane(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.close_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_open_artifact_pane(self) -> None:
        if self.state.artifact_pane_open or not self.state.phase_has_artifacts():
            return
        self.state.open_artifact_pane()
        self._sync_ui(force=True)
        self._apply_focus()

    def on_artifact_pane_closed(self, event: ArtifactPaneClosed) -> None:
        event.stop()
        self.action_close_artifact_pane()

    def on_artifact_pane_opened(self, event: ArtifactPaneOpened) -> None:
        event.stop()
        self.action_open_artifact_pane()

    def action_artifact_prev(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.move_artifact(-1)
        self._sync_ui(force=True)

    def action_artifact_next(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.move_artifact(1)
        self._sync_ui(force=True)

    def action_artifact_left(self) -> None:
        self.action_artifact_prev()

    def action_artifact_right(self) -> None:
        self.action_artifact_next()

    def action_nav_up(self) -> None:
        if self.state.focus_target == "artifact":
            self.query_one(ArtifactPane).scroll_by(-1)
            return
        self.state.focus_target = "phases"
        self.state.move_nav(-1)
        self._sync_ui(force=True)

    def action_nav_down(self) -> None:
        if self.state.focus_target == "artifact":
            self.query_one(ArtifactPane).scroll_by(1)
            return
        self.state.focus_target = "phases"
        self.state.move_nav(1)
        self._sync_ui(force=True)

    def on_nav_selected(self, event: NavSelected) -> None:
        self.state.select_phase(event.index)
        self.state.focus_target = "phases"
        self._sync_ui(force=True)

    def on_artifact_tab_selected(self, event: ArtifactTabSelected) -> None:
        self.state.select_artifact(event.path)
        self.state.focus_target = "artifact"
        self._sync_ui(force=True)

    def action_back_list(self) -> None:
        self.app.pop_screen()


def _pending_run(item: HistoryItem) -> tuple[str, str] | None:
    """Id e resumo da run, quando ainda há step por fazer.

    Qualquer workflow é retomável: a sessão ACP é isolada por step, então
    retomar é rodar o primeiro step que não terminou.
    """
    if not item.is_incomplete:
        return None
    done = sum(1 for step in item.steps if step.status in {"done", "skipped"})
    current = next(
        (step.label for step in item.steps if step.status not in {"done", "skipped"}),
        "—",
    )
    return item.run_id, f"{current} · steps {done}/{len(item.steps)}"
