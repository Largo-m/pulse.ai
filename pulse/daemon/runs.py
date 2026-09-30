from __future__ import annotations

import threading
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.orchestrator.engine import run_workflow
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store.workflow_defs import get_workflow, list_workflows


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
        run_id = str(uuid.uuid4())
        bus = EventBus()
        correlator = PromptCorrelator(bus)

        def _publish_control(kind: str) -> None:
            bus.publish({"type": f"run.{kind}", "run_id": run_id})

        state = RunState(
            id=run_id,
            workflow_id=workflow_id,
            prompt=prompt,
            workspace=workspace or str(Path.cwd()),
            bus=bus,
            correlator=correlator,
            control=RunControl(on_change=_publish_control),
            resume_run_id=resume_run_id,
        )
        with self._lock:
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

    def cancel(self, run_id: str) -> bool:
        """Corta o step em voo e encerra a run. Retomável por `resume_run_id`."""
        state = self.get(run_id)
        if state is None:
            return False
        state.cancel_requested = True
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
            )
        except Exception as error:
            # O traceback vai para o stderr do daemon (`~/.pulse/daemon.log`):
            # daqui para cima só sobrevive a mensagem, e uma run que morre por
            # um tipo de exceção inesperado precisa deixar onde olhar.
            traceback.print_exc()
            state.status = "failed"
            state.exit_code = 1
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
        else:
            state.status = "failed"
        state.bus.publish(
            {
                "type": "run.finished",
                "run_id": state.id,
                "exit_code": exit_code,
            }
        )
        state.bus.close()
