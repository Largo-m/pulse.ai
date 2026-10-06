from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pulse.config.paths import safe_cwd
from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.orchestrator.engine import RUN_BLOCKED, run_workflow
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store import runs as run_store
from pulse.store.runs import AWAITING_INPUT
from pulse.store.workflow_defs import get_workflow, list_workflows

#: Quanto tempo uma run encerrada continua anexável em memória. Depois disso o
#: replay some e quem quiser revê-la usa o histórico, que lê do banco.
FINISHED_TTL = 15 * 60.0
#: Teto de runs encerradas guardadas, independente do TTL.
FINISHED_KEEP = 10


@dataclass
class RunState:
    id: str
    workflow_id: str
    prompt: str
    workspace: str
    status: str = "running"
    exit_code: int | None = None
    bus: EventBus = field(default_factory=EventBus)
    correlator: PromptCorrelator | None = None
    cancel_requested: bool = False
    control: RunControl | None = None
    #: Run anterior a retomar, do primeiro step que não fechou.
    resume_run_id: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def is_active(self) -> bool:
        return self.finished_at is None


class RunAlreadyActive(Exception):
    """Retomar uma run que já está rodando. O id é o mesmo; a run também."""


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def list_workflows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item.id,
                "label": item.label,
                "description": item.description,
                "is_default": item.is_default,
                "default_prompt": item.default_prompt,
                "steps": [
                    {"id": step.step_id, "label": step.label, "agent": step.agent_id}
                    for step in item.steps
                ],
            }
            for item in list_workflows()
        ]

    def start_run(
        self,
        *,
        workflow_id: str,
        prompt: str,
        workspace: str | None = None,
        resume_run_id: str | None = None,
    ) -> RunState:
        if get_workflow(workflow_id) is None:
            raise ValueError(f"workflow desconhecido: {workflow_id}")
        # Retomar continua a mesma run, então ela mantém o id — é isso que faz
        # `RunState.id` e `runs.id` no SQLite serem a mesma coisa, e o que
        # permite anexar numa run pelo id em vez de chutar a mais recente.
        run_id = resume_run_id or str(uuid.uuid4())
        self._prune()
        bus = EventBus()
        correlator = PromptCorrelator(bus)

        def _publish_control(kind: str) -> None:
            bus.publish({"type": f"run.{kind}", "run_id": run_id})

        state = RunState(
            id=run_id,
            workflow_id=workflow_id,
            prompt=prompt,
            workspace=workspace or str(safe_cwd()),
            bus=bus,
            correlator=correlator,
            control=RunControl(on_change=_publish_control),
            resume_run_id=resume_run_id,
        )
        # Checar e registrar sob o mesmo lock: dois "retomar" da mesma run ao
        # mesmo tempo (endpoints síncronos rodam num threadpool) passariam os
        # dois por uma checagem feita antes.
        with self._lock:
            existing = self._runs.get(run_id)
            if existing is not None and existing.is_active():
                raise RunAlreadyActive(f"run já está em execução: {run_id}")
            self._runs[run_id] = state
        thread = threading.Thread(
            target=self._execute,
            args=(state,),
            name=f"pulse-run-{run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return state

    def get(self, run_id: str) -> RunState | None:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        """As runs que o daemon tem em memória — ativas primeiro, mais nova no topo.

        É o que a Home consulta para saber que há algo rodando em background e o
        que o cockpit usa para reabrir sem recriar nada.
        """
        with self._lock:
            states = list(self._runs.values())
        labels = {item.id: item.label for item in list_workflows()}
        items = [self._describe(state, labels) for state in states]
        items.sort(key=lambda item: (not item["active"], -item["started_at"]))
        return items

    def _describe(self, state: RunState, labels: dict[str, str]) -> dict[str, Any]:
        awaiting = bool(state.correlator is not None and state.correlator.pending())
        since = state.correlator.pending_since() if state.correlator is not None else None
        return {
            "id": state.id,
            "workflow_id": state.workflow_id,
            "workflow_label": labels.get(state.workflow_id, state.workflow_id),
            "prompt": state.prompt,
            "workspace": state.workspace,
            # `awaiting_input` é derivado, não guardado: `RunState.status` é o
            # desfecho da run, e esperar não é desfecho nenhum. Quem lista
            # precisa ver a diferença entre uma run trabalhando e uma parada
            # esperando resposta.
            "status": AWAITING_INPUT if (awaiting and state.is_active()) else state.status,
            "active": state.is_active(),
            "awaiting_prompt": awaiting,
            "awaiting_since": since,
            "current_step_label": self._current_step_label(state),
            "started_at": state.started_at,
            "exit_code": state.exit_code,
        }

    @staticmethod
    def _current_step_label(state: RunState) -> str:
        """Em que passo a run está, lido do banco — a fonte que o motor atualiza.

        Banco indisponível não vale derrubar a listagem: a Home mostra a run sem
        o passo em vez de não mostrar a run.
        """
        try:
            record = run_store.load_run(state.id)
        except (OSError, ValueError):
            return ""
        if record is None:
            return ""
        step = record.step(record.current_step) if record.current_step else None
        return step.label if step is not None else ""

    def _prune(self) -> None:
        """Solta as runs encerradas que ninguém vai mais anexar.

        O replay vive no `EventBus` de cada run; guardar todas para sempre é
        vazamento. O passado continua no banco — o que se perde aqui é só a
        possibilidade de reabrir a run *ao vivo*, que para run encerrada não
        existe mesmo.
        """
        now = time.time()
        with self._lock:
            finished = [
                state
                for state in self._runs.values()
                if state.finished_at is not None
            ]
            finished.sort(key=lambda state: state.finished_at or 0.0, reverse=True)
            for index, state in enumerate(finished):
                stale = now - (state.finished_at or now) > FINISHED_TTL
                if stale or index >= FINISHED_KEEP:
                    self._runs.pop(state.id, None)

    def cancel(self, run_id: str) -> bool:
        """Corta o step em voo e encerra a run. Retomável por `resume_run_id`."""
        state = self.get(run_id)
        if state is None:
            return False
        state.cancel_requested = True
        # Antes do `stop`: uma run parada no meio de uma pergunta está bloqueada
        # esperando resposta sem prazo, e o pedido de parada sozinho não acorda
        # quem está nesse `wait`. Cancelar devolve `None` ao motor, que é o
        # mesmo que a pessoa fechar a pergunta.
        if state.correlator is not None:
            state.correlator.cancel_all()
        if state.control is not None:
            state.control.stop()
        state.bus.publish({"type": "run.cancel_requested", "run_id": state.id})
        return True

    def answer_prompt(self, prompt_id: str, answer: Any) -> bool:
        with self._lock:
            runs = list(self._runs.values())
        for state in runs:
            if state.correlator is not None and state.correlator.answer(prompt_id, answer):
                return True
        return False

    def _execute(self, state: RunState) -> None:
        assert state.correlator is not None
        stream = ApiStreamSink(state.bus)
        prompt_handler = ApiPromptPort(state.correlator)
        state.bus.publish(
            {
                "type": "run.started",
                "run_id": state.id,
                "workflow_id": state.workflow_id,
            }
        )
        try:
            exit_code = run_workflow(
                workflow_id=state.workflow_id,
                user_prompt=state.prompt,
                workspace=Path(state.workspace) if state.workspace else None,
                stream=stream,
                prompt_handler=prompt_handler,
                render_header=False,
                resume_run_id=state.resume_run_id,
                control=state.control,
                run_id=state.id,
            )
        except Exception as error:
            # O traceback vai para o stderr do daemon (`~/.pulse/daemon.log`):
            # daqui para cima só sobrevive a mensagem, e uma run que morre por
            # um tipo de exceção inesperado precisa deixar onde olhar.
            traceback.print_exc()
            state.status = "failed"
            state.exit_code = 1
            state.finished_at = time.time()
            state.bus.publish(
                {
                    "type": "run.finished",
                    "run_id": state.id,
                    "exit_code": 1,
                    "error": str(error),
                }
            )
            state.bus.close()
            return
        state.exit_code = exit_code
        if exit_code == 0:
            state.status = "completed"
        elif exit_code == RUN_STOPPED:
            state.status = "stopped"
        elif exit_code == RUN_BLOCKED:
            # Nada quebrou: um step declarou que não tinha como entregar e a run
            # não passou por cima. Quem consulta a API precisa ver a diferença.
            state.status = "blocked"
        else:
            state.status = "failed"
        state.finished_at = time.time()
        state.bus.publish(
            {
                "type": "run.finished",
                "run_id": state.id,
                "exit_code": exit_code,
            }
        )
        state.bus.close()
