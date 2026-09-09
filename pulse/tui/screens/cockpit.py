from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.adapters.prompt_bridge import PromptBridge, TextualPromptHandler
from pulse.tui.state import CockpitState
from pulse.tui.widgets.app_footer import AppFooter
from pulse.tui.widgets.app_header import AppHeader
from pulse.tui.widgets.log_stream import LogStream
from pulse.tui.widgets.phase_sidebar import PhaseSelected, PhaseSidebar
from pulse.tui.widgets.prompt_modal import PromptModal


class CockpitScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_or_back", "Quit"),
        ("tab", "toggle_focus", "Focus"),
        ("up", "phase_up", "Up"),
        ("down", "phase_down", "Down"),
        ("k", "phase_up", "Up"),
        ("j", "phase_down", "Down"),
    ]

    def __init__(self, workflow_id: str, user_prompt: str) -> None:
        super().__init__()
        self.workflow_id = workflow_id
        self.user_prompt = user_prompt
        self.state = CockpitState()
        self.state.configure_workflow(workflow_id)
        self.bridge = PromptBridge()
        self.sink = CockpitSink(
            self.state,
            on_change=self._on_state_change,
            cwd=str(Path.cwd()),
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
        yield AppFooter()

    def on_mount(self) -> None:
        self._sync_ui(force=True)
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
        self.query_one(AppHeader).sync_from_state(self.state)
        self.query_one(PhaseSidebar).sync_from_state(self.state)
        self.query_one(LogStream).sync_from_state(self.state, force=force)
        self.query_one(AppFooter).sync_from_state(self.state)

    def _poll_prompts(self) -> None:
        if self._prompt_open:
            return
        request = self.bridge.poll()
        if request is None:
            return
        self._prompt_open = True

        def _finish(result: object | None) -> None:
            self._prompt_open = False
            if request.future is not None and not request.future.done():
                request.future.set_result(result)

        self.app.push_screen(PromptModal(request), _finish)

    def _run_workflow(self) -> None:
        from pulse.plan.runner import run_plan

        try:
            code = run_plan(
                spec_type_id=self.workflow_id,
                user_prompt=self.user_prompt,
                stream=self.sink,
                prompt_handler=self.prompt_handler,
                render_header=False,
            )
        except Exception as error:
            self.state.add_info(f"Erro: {error}")
            self._dirty = True
            code = 1
        self.state.mark_finished(code)
        self._dirty = True
        try:
            self.app.call_from_thread(self._on_workflow_done, code)
        except Exception:
            pass

    def _on_workflow_done(self, code: int) -> None:
        self.state.add_info(f"Workflow finalizado · exit {code}")
        self._sync_ui(force=True)

    def action_toggle_focus(self) -> None:
        self.state.toggle_focus()
        self._sync_ui(force=True)
        if self.state.focus_target == "phases":
            self.query_one(PhaseSidebar).focus()
        else:
            self.query_one(LogStream).focus()

    def action_phase_up(self) -> None:
        if self.state.focus_target != "phases":
            return
        self.state.move_phase(-1)
        self._sync_ui(force=True)

    def action_phase_down(self) -> None:
        if self.state.focus_target != "phases":
            return
        self.state.move_phase(1)
        self._sync_ui(force=True)

    def on_phase_selected(self, event: PhaseSelected) -> None:
        self.state.select_phase(event.index)
        self.state.focus_target = "phases"
        self._sync_ui(force=True)

    def action_quit_or_back(self) -> None:
        if self.state.running:
            self.bridge.close()
            self.state.mark_finished(1)
        self.app.pop_screen()
