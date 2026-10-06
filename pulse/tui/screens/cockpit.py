from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen

from pulse.orchestrator.engine import RUN_BLOCKED
from pulse.runcontrol import RUN_STOPPED
from pulse.tui.adapters.cockpit_sink import CockpitSink
from pulse.tui.adapters.prompt_bridge import (
    PromptAbandoned,
    PromptBridge,
    TextualPromptHandler,
)
from pulse.tui.screens.resume_choice import RESUME, ResumeChoiceScreen
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
    #
    # Sair (`escape_back`/`back_to_menu`) não está nesta lista de propósito: a
    # run segue no daemon e a pergunta continua pendente, esperando a pessoa
    # voltar. Parar, que decide pelo agente, continua bloqueado.
    "stop_run",
    "toggle_artifact_pane",
    "close_artifact_pane",
    "artifact_left",
    "artifact_right",
    "artifact_prev",
    "artifact_next",
}


class CockpitScreen(Screen[None]):
    BINDINGS = [
        Binding("q", "back_to_menu", "Menu"),
        Binding("b", "back_to_menu", "Menu"),
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
        resume_run_id: str | None = None,
        attach_run_id: str | None = None,
    ) -> None:
        super().__init__()
        self.workflow_id = workflow_id
        self.user_prompt = user_prompt
        self.resume_run_id = resume_run_id
        #: Run que já está rodando no daemon. A tela escuta em vez de criar.
        self.attach_run_id = attach_run_id
        self.state = CockpitState()
        self.state.configure_workflow(workflow_id)
        self.bridge = PromptBridge()
        #: A raiz do projeto: é com ela que o daemon resolve a config e é por
        #: ela que as runs deste workspace são encontradas.
        self._workspace = str(workspace or Path.cwd())
        #: Onde a run trabalha — igual à raiz, até o `run.context` dizer que é
        #: um worktree. Só o painel de artefatos e os caminhos de arquivo usam.
        self._cwd = self._workspace
        self.sink = CockpitSink(
            self.state,
            on_change=self._on_state_change,
            cwd=self._cwd,
            on_replay_end=self._on_replay_end,
            on_context=self._on_context,
        )
        self.prompt_handler = TextualPromptHandler(self.bridge)
        self._worker = None
        self._dirty = False
        self._prompt_open = False
        #: Criada na thread da run; as teclas de controle falam com ela por HTTP.
        self._session = None
        #: Ligado ao sair: a run continua, esta tela é que acabou.
        self._detached = False
        #: Ligado quando o stream da run acabou de verdade (`run.finished` ou
        #: erro). Até lá a run está viva no daemon, tenha ela aberto step ou não.
        self._run_over = False

    def compose(self) -> ComposeResult:
        yield AppHeader()
        with Horizontal(id="cockpit-body"):
            yield PhaseSidebar(self.state, id="phase-sidebar")
            yield LogStream(self.state, id="log-stream")
            yield ArtifactPane(self.state, cwd=self._cwd, id="artifact-pane")
        yield AppFooter()

    def on_mount(self) -> None:
        self._restore_previous_run()
        self._sync_ui(force=True)
        self._apply_focus()
        self.set_interval(0.08, self._flush_ui)
        self.set_interval(0.1, self._poll_prompts)
        self._worker = self.run_worker(self._run_workflow, exclusive=True, thread=True)

    def on_unmount(self) -> None:
        """A tela morreu. Se a run não morreu junto, nada aqui a responde.

        Vale tanto para o `q` (que já desanexou) quanto para sair do Pulse com
        o cockpit aberto: o daemon é outro processo, a run continua lá e a
        pergunta aberta tem que continuar esperando. Só quando a run já acabou
        é que cancelar o que sobrou é a verdade.
        """
        if self._run_alive():
            self._detached = True
            session = self._session
            if session is not None:
                session.detach()
            self.bridge.abandon()
            return
        self.bridge.close()

    def _run_alive(self) -> bool:
        """A run ainda existe no daemon — a pergunta é se esta tela a solta.

        Não é `state.running`: esse só liga no primeiro `phase.begin`. Antes
        dele a run já está no daemon (resolvendo config, abrindo o worktree), e
        sair nessa janela fechava a ponte sem desanexar — a sessão seguia
        ouvindo com a ponte fechada e respondia "cancelado" sozinha a toda
        pergunta que a run fizesse depois, inclusive às da tela reanexada.
        """
        return not self._run_over

    def _restore_previous_run(self) -> None:
        """Retomar continua a mesma run: a tela abre com o passado dela.

        Sem isto o cockpit nascia vazio e os steps que já tinham fechado voltavam
        como "concluído" e nada mais — sem log, sem tool e sem duração.

        Anexar não passa por aqui: lá quem reconstrói é o replay do barramento,
        que devolve a run inteira pelo mesmo caminho do vivo.
        """
        if self.attach_run_id or not self.resume_run_id:
            return
        from pulse.tui.hydrate import restore_run

        try:
            exec_root = restore_run(self.state, self.resume_run_id, Path(self._workspace))
            if exec_root:
                self._cwd = exec_root
                self.sink.set_cwd(exec_root)
        except (OSError, ValueError):
            # Histórico é contexto, não requisito: não vale impedir a run de
            # continuar porque o banco não abriu.
            pass

    def _on_replay_end(self) -> None:
        """Fim do replay: acertar o relógio, que o replay não reproduz.

        Os `phase.begin` reaplicados marcaram "agora" como início de cada step;
        quem sabe a hora de verdade é `run_steps`.
        """
        if not self.attach_run_id:
            return
        from pulse.tui.hydrate import stamp_live_elapsed

        try:
            stamp_live_elapsed(self.state, self.attach_run_id)
        except (OSError, ValueError):
            # Duração é acabamento: não vale derrubar a run reanexada por isso.
            pass
        self._dirty = True

    def _on_context(self, cwd: str) -> None:
        """A run disse onde trabalha — o painel de artefatos tem que ir junto.

        Chega da thread da run, então nada de `query_one` aqui: o painel é
        reapontado no próximo `_sync_ui`, que roda no laço da tela.
        """
        if not cwd or cwd == self._cwd:
            return
        self._cwd = cwd
        self._dirty = True

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
        pane = self.query_one(ArtifactPane)
        pane.set_cwd(self._cwd)
        pane.sync_from_state(self.state, force=force)
        self.query_one(AppFooter).sync_from_state(self.state)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if self._prompt_open and action in _PROMPT_BLOCKED:
            return False
        if self._prompt_open and action in {"nav_up", "nav_down"}:
            if self.state.focus_target != "phases":
                return False
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
        self.state.select_artifact_from_prompt(f"{request.prompt}\n{request.title}")
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
        from pulse.client.run_session import DETACHED, EngineRunSession

        try:
            session = EngineRunSession(
                stream=self.sink,
                prompt_handler=self.prompt_handler,
            )
            self._session = session
            if self.attach_run_id:
                code = session.attach(self.attach_run_id)
            else:
                code = session.run(
                    workflow_id=self.workflow_id,
                    user_prompt=self.user_prompt,
                    workspace=self._workspace,
                    resume_run_id=self.resume_run_id,
                )
        except PromptAbandoned:
            # Saímos da tela com uma pergunta aberta. A run segue no daemon.
            return
        except Exception as error:
            if self._detached:
                return
            self.state.add_error("Workflow falhou", str(error))
            self._dirty = True
            code = 1
        if code == DETACHED:
            return
        self._run_over = True
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
            self._offer_resume()
            return
        elif code == RUN_BLOCKED:
            # "Falhou" seria a palavra errada: o agente rodou e disse que não
            # tinha como entregar. O que resolve é destravar e retomar.
            self.state.add_info(
                "Run bloqueada — resolva o que o step pediu e retome de onde parou"
            )
            self._sync_ui(force=True)
            self._offer_resume()
            return
        else:
            if not self.state.has_error():
                self.state.add_error(
                    "Workflow falhou",
                    f"O fluxo encerrou com código {code}.",
                )
            # Falha também é run pela metade: o que já rodou está em
            # `run_steps`, então oferecer retomar aqui evita mandar o usuário
            # ao histórico só para descobrir que dá para continuar.
            if self._resumable_run() is not None:
                self.state.add_info("Dá para retomar do step que falhou")
            self._sync_ui(force=True)
            self._offer_resume()
            return
        self._sync_ui(force=True)

    def action_stop_run(self) -> None:
        """`s` corta o step em execução e encerra a run — retomável depois."""
        session = self._session
        if session is None or not self.state.running or not self.state.can_stop:
            return
        session.stop()
        # O corte do turno leva alguns instantes; o estado real chega pelo
        # evento `run.stopped`, mas a intenção aparece na hora.
        self.state.add_info("Parando — cortando o step em execução")
        self._sync_ui(force=True)

    def _offer_resume(self) -> None:
        """Depois de parar, oferece o mesmo retomar do histórico."""
        pending = self._resumable_run()
        if pending is None:
            return
        run_id, summary = pending

        def _chosen(mode: str | None) -> None:
            if mode != RESUME:
                return
            self.app.pop_screen()
            self.app.open_cockpit(
                self.workflow_id,
                self.user_prompt,
                resume_run_id=run_id,
            )

        self.app.push_screen(
            ResumeChoiceScreen(slug=summary, summary=summary),
            callback=_chosen,
        )

    def _resumable_run(self) -> tuple[str, str] | None:
        """Run parada que dá para retomar: a desta tela, ou a mais recente."""
        from pulse.store import runs as run_store

        # Com N runs vivas, "a mais recente do workspace" pode ser a de outra
        # tela. Quando esta run tem id conhecido é por ele que se pergunta.
        known = self.attach_run_id or self.resume_run_id
        try:
            if known:
                record = run_store.load_run(known)
                pending = [record] if record is not None and record.is_incomplete() else []
            else:
                # Pela raiz do projeto, não pelo `_cwd`: com worktree o `_cwd`
                # é o diretório da run, e nenhuma run é indexada por ele.
                pending = run_store.find_resumable(Path(self._workspace))
        except (OSError, ValueError):
            return None
        if not pending:
            return None
        newest = max(pending, key=lambda item: item.updated_at or item.created_at)
        return newest.id, _run_summary(newest)

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
        self.state.select_phase(event.index)
        self.state.focus_target = "phases"
        self._sync_ui(force=True)

    def on_artifact_tab_selected(self, event: ArtifactTabSelected) -> None:
        self.state.select_artifact(event.path)
        if not self._prompt_open:
            self.state.focus_target = "artifact"
        self._sync_ui(force=True)

    def action_back_to_menu(self) -> None:
        """Sair é largar a tela, não a run.

        A run vive no daemon, então sair só desliga este observador: o stream é
        solto e as perguntas abertas continuam pendentes lá, esperando a pessoa
        voltar. A Home mostra a run e reabre por ela.
        """
        if self._run_alive():
            self._detached = True
            session = self._session
            if session is not None:
                session.detach()
            self.bridge.abandon()
        self.app.pop_screen()


def _run_summary(record) -> str:
    """Onde a run parou, para a tela de escolha."""
    done = sum(1 for step in record.steps if step.status in {"done", "skipped"})
    current = record.current_step or (record.steps[0].step_id if record.steps else "—")
    return f"{current} · steps {done}/{len(record.steps)}"
