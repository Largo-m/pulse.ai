from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.adapters.prompt_bridge import PromptBridge, TextualPromptHandler
from pulse.tui.state import CockpitState
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

_PROMPT_BLOCKED = {
    "toggle_artifact_pane",
    "close_artifact_pane",
    "escape_back",
    "back_to_menu",
    "artifact_left",
    "artifact_right",
    "artifact_prev",
    "artifact_next",
}


class CockpitScreen(Screen[None]):
    BINDINGS = [
        Binding("q", "back_to_menu", "Menu"),
        Binding("b", "back_to_menu", "Menu"),
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

    def __init__(
        self,
        workflow_id: str,
        user_prompt: str,
        *,
        workspace: Path | None = None,
    ) -> None:
        super().__init__()
        self.workflow_id = workflow_id
        self.user_prompt = user_prompt
        self.state = CockpitState()
        self.state.configure_workflow(workflow_id)
        self.bridge = PromptBridge()
        self._cwd = str(workspace or Path.cwd())
        self.sink = CockpitSink(
            self.state,
            on_change=self._on_state_change,
            cwd=self._cwd,
        )
        self.prompt_handler = TextualPromptHandler(self.bridge)
        self._worker = None
        self._dirty = False
        self._prompt_open = False

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="cockpit-body"):
            yield PhaseSidebar(self.state, id="phase-sidebar")
            yield LogStream(self.state, id="log-stream")
            yield ArtifactPane(self.state, cwd=self._cwd, id="artifact-pane")
        yield AppFooter()

    def on_mount(self) -> None:
        self._sync_ui(force=True)
        self._apply_focus()
        self.set_interval(0.08, self._flush_ui)
        self.set_interval(0.1, self._poll_prompts)
        self._worker = self.run_worker(self._run_workflow, exclusive=True, thread=True)

    def on_unmount(self) -> None:
        self.bridge.close()

    def _on_state_change(self) -> None:
        self._dirty = True

    def _flush_ui(self) -> None:
        if not self._dirty:
            return
        self._dirty = False
        self._sync_ui()

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
        if self._prompt_open and action in _PROMPT_BLOCKED:
            return False
        if self._prompt_open and action in {"nav_up", "nav_down"}:
            if self.state.focus_target != "phases":
                return False
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
        self.action_back_to_menu()

    def _poll_prompts(self) -> None:
        if self._prompt_open:
            return
        request = self.bridge.poll()
        if request is None:
            return
        self._prompt_open = True
        self.state.reveal_artifact_from_prompt(f"{request.prompt}\n{request.title}")
        self._sync_ui(force=True)

        def _finish(result: object | None) -> None:
            self._prompt_open = False
            if request.future is not None and not request.future.done():
                request.future.set_result(result)
            if self.is_mounted:
                try:
                    self.query_one(LogStream).focus()
                except Exception:
                    pass

        self.query_one(LogStream).show_prompt(request, _finish)

    def _run_workflow(self) -> None:
        from pulse.client.run_session import EngineRunSession

        try:
            session = EngineRunSession(
                stream=self.sink,
                prompt_handler=self.prompt_handler,
            )
            code = session.run(
                workflow_id=self.workflow_id,
                user_prompt=self.user_prompt,
                workspace=self._cwd,
            )
        except Exception as error:
            self.state.add_error("Workflow falhou", str(error))
            self._dirty = True
            code = 1
        self.state.mark_finished(code)
        self._dirty = True
        try:
            self.app.call_from_thread(self._on_workflow_done, code)
        except Exception:
            pass

    def _on_workflow_done(self, code: int) -> None:
        if code == 0:
            self.state.add_info("Workflow concluído")
        elif not self.state.has_error():
            self.state.add_error(
                "Workflow falhou",
                f"O fluxo encerrou com código {code}.",
            )
        self._sync_ui(force=True)

    def _apply_focus(self) -> None:
        if self.state.focus_target == "phases":
            self.query_one(PhaseSidebar).focus()
        elif self.state.focus_target == "artifact" and self.state.artifact_pane_open:
            self.query_one(ArtifactPane).focus()
        elif self._prompt_open and self.query_one(LogStream).focus_prompt():
            return
        else:
            self.query_one(LogStream).focus()

    def action_toggle_focus(self) -> None:
        self.state.toggle_focus()
        self._sync_ui(force=True)
        self._apply_focus()

    def action_toggle_artifact_pane(self) -> None:
        self.state.toggle_artifact_pane()
        self._sync_ui(force=True)
        if not self._prompt_open:
            self._apply_focus()

    def action_close_artifact_pane(self) -> None:
        if not self.state.artifact_pane_open:
            return
        self.state.close_artifact_pane()
        self._sync_ui(force=True)
        if not self._prompt_open:
            self._apply_focus()

    def action_open_artifact_pane(self) -> None:
        if self.state.artifact_pane_open or not self.state.phase_has_artifacts():
            return
        self.state.open_artifact_pane()
        self._sync_ui(force=True)
        if not self._prompt_open:
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
        if event.kind == "task":
            self.state.select_task(event.index)
        else:
            self.state.select_phase(event.index)
        self.state.focus_target = "phases"
        self._sync_ui(force=True)

    def on_artifact_tab_selected(self, event: ArtifactTabSelected) -> None:
        self.state.select_artifact(event.path)
        if not self._prompt_open:
            self.state.focus_target = "artifact"
        self._sync_ui(force=True)

    def action_back_to_menu(self) -> None:
        if self.state.running:
            self.bridge.close()
        self.app.pop_screen()
