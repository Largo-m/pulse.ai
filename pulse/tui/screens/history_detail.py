from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.history.models import HistoryItem
from pulse.history.run_log import RunLog
from pulse.tui import engine, strings
from pulse.tui.hydrate import hydrate_history_item
from pulse.tui.screens.confirm import ConfirmScreen
from pulse.tui.screens.navigation import pulse_app
from pulse.tui.screens.resume_choice import RESUME, ResumeChoiceScreen, resume_summary
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
        Binding("q", "back_list", strings.BACK),
        Binding("r", "resume_workflow", strings.BINDING_RESUME),
        Binding("w", "remove_worktree", strings.BINDING_REMOVE_WORKTREE),
        Binding("b", "back_list", strings.BACK),
        Binding("tab", "toggle_focus", strings.BINDING_FOCUS),
        Binding("a", "toggle_artifact_pane", strings.BINDING_ARTIFACTS),
        Binding("escape", "escape_back", strings.BINDING_BACK),
        Binding("left_square_bracket", "artifact_prev", strings.BINDING_PREV_FILE),
        Binding("right_square_bracket", "artifact_next", strings.BINDING_NEXT_FILE),
        Binding("left", "artifact_left", strings.BINDING_PREV_FILE),
        Binding("right", "artifact_right", strings.BINDING_NEXT_FILE),
        Binding("up", "nav_up", strings.BINDING_UP, priority=True),
        Binding("down", "nav_down", strings.BINDING_DOWN, priority=True),
        Binding("k", "nav_up", strings.BINDING_UP, priority=True),
        Binding("j", "nav_down", strings.BINDING_DOWN, priority=True),
    ]

    def __init__(self, item: HistoryItem, workspace: Path | None = None) -> None:
        super().__init__()
        self.item = item
        self._workspace = Path(workspace or Path.cwd())
        self._cwd = item.worktree_path or str(self._workspace)
        self.state = hydrate_history_item(item, Path(self._cwd), _run_log(item.run_id))
        shape = _workflow_shape(item.workflow_id)
        if shape is not None:
            self.state.base_labels = dict(shape.steps)
        self._pending = _pending_run(item)

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="cockpit-body"):
            yield PhaseSidebar(self.state, id="phase-sidebar")
            yield LogStream(self.state, id="log-stream")
            yield ArtifactPane(self.state, cwd=self._cwd, id="artifact-pane")
        yield AppFooter(back_label=strings.FOOTER_BACK)

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
            pulse_app(self).open_cockpit(
                self.item.workflow_id,
                self.item.prompt,
                resume_run_id=run_id,
            )

        self.app.push_screen(
            ResumeChoiceScreen(slug=self.item.title, summary=summary),
            callback=_chosen,
        )

    def action_remove_worktree(self) -> None:
        """Remove this run's worktree after confirmation.

        Removal is manual because the worktree is the deliverable: the reviewer
        decides when they are done with it. A run the daemon still executes keeps
        it: the agent works there and the daemon would write the path back.
        """
        if not self.item.worktree_path:
            return
        try:
            worktree = engine.worktree_state(self._workspace, self.item.item_id)
        except engine.EngineUnavailable as error:
            self.notify(strings.ENGINE_UNAVAILABLE.format(error=error))
            return
        if worktree is None or not worktree.exists:
            return
        if worktree.active:
            self.notify(strings.WORKTREE_KEPT_RUN_ACTIVE)
            return
        detail = [worktree.path, strings.WORKTREE_BRANCH.format(branch=self.item.branch or "—")]
        if worktree.dirty:
            detail.append(strings.WORKTREE_DIRTY)
        else:
            detail.append(strings.WORKTREE_CLEAN)

        self.app.push_screen(
            ConfirmScreen(
                title=strings.CONFIRM_TITLE_REMOVE_WORKTREE,
                detail="\n".join(detail),
                confirm_label=strings.REMOVE,
            ),
            callback=self._remove_confirmed,
        )

    def _remove_confirmed(self, confirmed: bool | None) -> None:
        if not confirmed:
            return
        try:
            removed = engine.remove_worktree(self._workspace, self.item.item_id)
        except engine.WorktreeInUse:
            self.notify(strings.WORKTREE_KEPT_RUN_ACTIVE)
            return
        except engine.EngineUnavailable as error:
            self.notify(strings.ENGINE_UNAVAILABLE.format(error=error))
            return
        if not removed:
            self.notify(strings.WORKTREE_GIT_REFUSED)
            return
        self.item.worktree_path = ""
        self.notify(strings.WORKTREE_REMOVED)

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

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
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
    """Run id and summary when there are still steps left to run.

    Any workflow is resumable: ACP sessions are per step, so resuming runs the
    first unfinished step.
    """
    if not item.is_incomplete:
        return None
    return item.run_id, resume_summary(item)


def _run_log(run_id: str) -> RunLog | None:
    """The run's persisted log; without the daemon, the steps show without it."""
    try:
        return engine.run_log(run_id)
    except engine.EngineUnavailable:
        return None


def _workflow_shape(workflow_id: str) -> engine.WorkflowShape | None:
    try:
        return engine.workflow(workflow_id)
    except engine.EngineUnavailable:
        return None
