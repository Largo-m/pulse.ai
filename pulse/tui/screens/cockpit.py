from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.runcontrol import RUN_STOPPED
from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.adapters.prompt_bridge import PromptBridge, TextualPromptHandler
from pulse.tui.screens.resume_choice import RESTART, RESUME, ResumeChoiceScreen
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
    # Com um prompt aberto quem está travado é o usuário, não o agente: cortar
    # o turno aqui deixaria a pergunta sem ninguém para respondê-la.
    "toggle_pause",
    "stop_run",
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
        Binding("p", "toggle_pause", "Pausar"),
        Binding("s", "stop_run", "Parar"),
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
        spec_slug: str | None = None,
        spec_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.workflow_id = workflow_id
        self.user_prompt = user_prompt
        self.spec_slug = spec_slug
        self.spec_mode = spec_mode
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
        #: Criada na thread da run; as teclas de controle falam com ela por HTTP.
        self._session = None

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
        if action == "toggle_pause":
            return self.state.running and self.state.can_pause and self._session is not None
        if action == "stop_run":
            return self.state.running and self.state.can_stop and self._session is not None
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
            self._session = session
            code = session.run(
                workflow_id=self.workflow_id,
                user_prompt=self.user_prompt,
                workspace=self._cwd,
                spec_slug=self.spec_slug,
                spec_mode=self.spec_mode,
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
        elif code == RUN_STOPPED:
            self.state.add_info("Run parada — dá para retomar de onde parou")
            self._sync_ui(force=True)
            self._offer_restart()
            return
        elif not self.state.has_error():
            self.state.add_error(
                "Workflow falhou",
                f"O fluxo encerrou com código {code}.",
            )
        self._sync_ui(force=True)

    def action_toggle_pause(self) -> None:
        """`p` pausa a run viva e retoma a pausada."""
        session = self._session
        if session is None or not self.state.running or not self.state.can_pause:
            return
        if self.state.paused:
            session.resume()
            return
        session.pause()
        # O corte do turno leva alguns instantes; o estado real chega pelo
        # evento `run.paused`, mas a intenção aparece na hora.
        self.state.add_info("Pausando — cortando o step em execução")
        self._sync_ui(force=True)

    def action_stop_run(self) -> None:
        session = self._session
        if session is None or not self.state.running or not self.state.can_stop:
            return
        session.stop()
        self.state.add_info("Parando a run")
        self._sync_ui(force=True)

    def _offer_restart(self) -> None:
        """Depois de parar, oferece o mesmo retomar/refazer do histórico."""
        pending = self._resumable_workflow()
        if pending is None:
            return
        slug, summary = pending

        def _chosen(mode: str | None) -> None:
            if mode not in {RESUME, RESTART}:
                return
            self.app.pop_screen()
            self.app.open_cockpit(
                self.workflow_id,
                self.user_prompt,
                spec_slug=slug,
                spec_mode=mode,
            )

        self.app.push_screen(
            ResumeChoiceScreen(slug=slug, summary=summary),
            callback=_chosen,
        )

    def _resumable_workflow(self) -> tuple[str, str] | None:
        from pulse.plan.specify_state import (
            find_resumable_workflows,
            find_workflow_by_slug,
            resume_summary,
            workflow_is_incomplete,
        )

        workspace = Path(self._cwd)
        try:
            if self.spec_slug:
                state = find_workflow_by_slug(workspace, self.spec_slug)
                if state is None or not workflow_is_incomplete(state):
                    return None
                return state.feature_slug, resume_summary(state)
            # Spec nova: o slug só existe depois que o agente criou a pasta, então
            # a run parada é a incompleta mais recente.
            pending = find_resumable_workflows(workspace)
        except (OSError, ValueError):
            return None
        if not pending:
            return None
        newest = max(pending, key=lambda item: item.updated_at or item.created_at)
        return newest.feature_slug, resume_summary(newest)

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
