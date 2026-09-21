from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.plan.runner import run_plan
from pulse.plan.spec_types import SPEC_TYPES, get_spec_type


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


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def list_workflows(self) -> list[dict[str, str]]:
        return [
            {"id": item.id, "label": item.label, "description": item.description}
            for item in SPEC_TYPES
        ]

    def start_run(
        self,
        *,
        workflow_id: str,
        prompt: str,
        workspace: str | None = None,
    ) -> RunState:
        if get_spec_type(workflow_id) is None:
            raise ValueError(f"workflow desconhecido: {workflow_id}")
        run_id = str(uuid.uuid4())
        bus = EventBus()
        correlator = PromptCorrelator(bus)
        state = RunState(
            id=run_id,
            workflow_id=workflow_id,
            prompt=prompt,
            workspace=workspace or str(Path.cwd()),
            bus=bus,
            correlator=correlator,
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
        state = self.get(run_id)
        if state is None:
            return False
        state.cancel_requested = True
        state.bus.publish({"type": "run.cancel_requested"})
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
            exit_code = run_plan(
                spec_type_id=state.workflow_id,
                user_prompt=state.prompt,
                stream=stream,
                prompt_handler=prompt_handler,
                render_header=False,
            )
        except Exception as error:
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
        state.status = "completed" if exit_code == 0 else "failed"
        state.bus.publish(
            {
                "type": "run.finished",
                "run_id": state.id,
                "exit_code": exit_code,
            }
        )
        state.bus.close()
