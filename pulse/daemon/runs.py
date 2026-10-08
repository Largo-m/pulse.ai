from __future__ import annotations

import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.config.agent_profiles import ConfiguredAgentProfiles
from pulse.daemon.adapters import ApiPromptPort, ApiStreamSink
from pulse.daemon.events import EventBus, PromptCorrelator
from pulse.doctor.checks import check_runtime_ready
from pulse.domain.control import SHUTDOWN_GRACE_SECONDS, RunControl
from pulse.domain.ports import PromptPort, StreamSink
from pulse.domain.run import RunStatus
from pulse.orchestrator.engine import run_workflow
from pulse.orchestrator.wiring import EnginePorts
from pulse.replies.permission import parse_policy
from pulse.store import runs as run_store
from pulse.store.paths import safe_cwd, worktrees_dir
from pulse.store.runs import SqliteRunRepository
from pulse.store.workflow_defs import get_workflow, list_workflows
from pulse.vcs.workspace import GitWorkspace

FINISHED_TTL = 15 * 60.0
FINISHED_KEEP = 10


@dataclass
class RunState:
    id: str
    workflow_id: str
    prompt: str
    workspace: str
    bus: EventBus
    correlator: PromptCorrelator
    control: RunControl
    status: RunStatus = RunStatus.RUNNING
    exit_code: int | None = None
    resume_run_id: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    ended: threading.Event = field(default_factory=threading.Event, compare=False, repr=False)

    @classmethod
    def open(
        cls,
        *,
        run_id: str,
        workflow_id: str,
        prompt: str,
        workspace: str,
        resume_run_id: str | None = None,
    ) -> RunState:
        """A new run with its own bus; questions and stop/pause go out on that bus."""
        bus = EventBus()

        def _publish_control(kind: str) -> None:
            bus.publish({"type": f"run.{kind}", "run_id": run_id})

        return cls(
            id=run_id,
            workflow_id=workflow_id,
            prompt=prompt,
            workspace=workspace,
            bus=bus,
            correlator=PromptCorrelator(bus),
            control=RunControl(on_change=_publish_control),
            resume_run_id=resume_run_id,
        )

    def is_active(self) -> bool:
        return self.finished_at is None

    def finish(self, exit_code: int) -> None:
        """The engine returned; record how the run ended."""
        if not self.is_active():
            raise RuntimeError(f"run {self.id} already finished")
        self.exit_code = exit_code
        self.status = RunStatus.for_exit_code(exit_code)
        self.finished_at = time.time()
        self.ended.set()


class RunAlreadyActive(Exception):
    """Raised when resuming a run that is already running."""


class UnknownWorkflow(ValueError):
    """Id that does not exist in `workflow_defs`."""


class DaemonShuttingDown(RuntimeError):
    """A run asked for after shutdown began; nobody would stop it before the daemon exits."""


def run_engine(
    *,
    workflow_id: str,
    user_prompt: str,
    workspace: Path | None,
    stream: StreamSink,
    prompt_handler: PromptPort,
    resume_run_id: str | None,
    control: RunControl,
    run_id: str,
) -> int:
    """Wire the engine's ports for one run, then run it.

    The only place that knows which adapter stands behind each port. The checks
    that need config, the database or the runtime happen here, before the engine
    spends a session.
    """
    definition = get_workflow(workflow_id)
    if definition is None:
        raise UnknownWorkflow(f"unknown workflow: {workflow_id}")
    resolved = resolve_config(workspace=workspace, workflow=workflow_id)
    runtime = resolved.runtime
    blocking = check_runtime_ready(runtime.id)
    if blocking is not None:
        raise RuntimeError(
            f"Runtime `{runtime.id}` unavailable: {blocking.message}. "
            f"{blocking.detail or ''}".strip()
        )
    session = AcpSessionRunner(
        resolved.acp_command,
        cwd=str(resolved.workspace_dir),
        permission_policy=parse_policy(resolved.permission_policy),
        stream=stream,
        prompt_handler=prompt_handler,
        runtime=runtime,
        control=control,
    )
    ports = EnginePorts(
        session=session,
        stream=stream,
        runs=SqliteRunRepository(),
        workspace=GitWorkspace(resolved.workspace_dir, worktrees=worktrees_dir()),
        agents=ConfiguredAgentProfiles(resolved.workspace_dir, fallback_model=resolved.model),
    )
    return run_workflow(
        definition=definition,
        user_prompt=user_prompt,
        ports=ports,
        use_worktree=resolved.use_worktree,
        resume_run_id=resume_run_id,
        control=control,
        run_id=run_id,
    )


class RunManager:
    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}
        self._lock = threading.Lock()
        self._closing = False

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
            raise UnknownWorkflow(f"unknown workflow: {workflow_id}")
        run_id = resume_run_id or str(uuid.uuid4())
        self._prune()
        state = RunState.open(
            run_id=run_id,
            workflow_id=workflow_id,
            prompt=prompt,
            workspace=workspace or str(safe_cwd()),
            resume_run_id=resume_run_id,
        )
        with self._lock:
            if self._closing:
                raise DaemonShuttingDown("the daemon is shutting down")
            existing = self._runs.get(run_id)
            if existing is not None and existing.is_active():
                raise RunAlreadyActive(f"run is already running: {run_id}")
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
        """Runs held in daemon memory: active first, newest on top.

        Home uses it to find background runs; the cockpit uses it to reattach.
        """
        with self._lock:
            states = list(self._runs.values())
        labels = {item.id: item.label for item in list_workflows()}
        items = [self._describe(state, labels) for state in states]
        items.sort(key=lambda item: (not item["active"], -item["started_at"]))
        return items

    def _describe(self, state: RunState, labels: dict[str, str]) -> dict[str, Any]:
        awaiting = bool(state.correlator.pending())
        since = state.correlator.pending_since()
        return {
            "id": state.id,
            "workflow_id": state.workflow_id,
            "workflow_label": labels.get(state.workflow_id, state.workflow_id),
            "prompt": state.prompt,
            "workspace": state.workspace,
            "status": RunStatus.AWAITING_INPUT
            if (awaiting and state.is_active())
            else state.status,
            "active": state.is_active(),
            "awaiting_prompt": awaiting,
            "awaiting_since": since,
            "current_step_label": self._current_step_label(state),
            "started_at": state.started_at,
            "exit_code": state.exit_code,
        }

    @staticmethod
    def _current_step_label(state: RunState) -> str:
        """The run's current step, read from the database the engine updates.

        A database error returns empty instead of breaking the listing.
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
        """Drop finished runs nobody will attach to anymore.

        Each run's replay lives in its `EventBus`; keeping them forever leaks
        memory. Past data remains in the database.
        """
        now = time.time()
        with self._lock:
            finished = [state for state in self._runs.values() if state.finished_at is not None]
            finished.sort(key=lambda state: state.finished_at or 0.0, reverse=True)
            for index, state in enumerate(finished):
                stale = now - (state.finished_at or now) > FINISHED_TTL
                if stale or index >= FINISHED_KEEP:
                    self._runs.pop(state.id, None)

    def cancel(self, run_id: str) -> bool:
        """Cut the in-flight step and end the run. Resumable via `resume_run_id`."""
        state = self.get(run_id)
        if state is None:
            return False
        self._stop(state)
        return True

    def shutdown(self, *, grace: float = SHUTDOWN_GRACE_SECONDS) -> list[str]:
        """Stop every active run and wait for each to end; return the ids still running.

        A stop is what ends a run cleanly: the engine records `RUN_STOPPED`, puts
        the step back to pending (resumable later) and closes the agent session,
        which terminates the ACP process. Without it, the daemon exited with
        runs left `running` and their agent processes orphaned.
        """
        with self._lock:
            self._closing = True
            active = [state for state in self._runs.values() if state.is_active()]
        for state in active:
            self._stop(state)
        deadline = time.monotonic() + grace
        return [
            state.id
            for state in active
            if not state.ended.wait(max(0.0, deadline - time.monotonic()))
        ]

    @staticmethod
    def _stop(state: RunState) -> None:
        state.correlator.cancel_all()
        state.control.stop()
        state.bus.publish({"type": "run.cancel_requested", "run_id": state.id})

    def answer_prompt(self, prompt_id: str, answer: object) -> bool:
        with self._lock:
            runs = list(self._runs.values())
        for state in runs:
            if state.correlator.answer(prompt_id, answer):
                return True
        return False

    def _execute(self, state: RunState) -> None:
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
            exit_code = run_engine(
                workflow_id=state.workflow_id,
                user_prompt=state.prompt,
                workspace=Path(state.workspace) if state.workspace else None,
                stream=stream,
                prompt_handler=prompt_handler,
                resume_run_id=state.resume_run_id,
                control=state.control,
                run_id=state.id,
            )
        except Exception as error:  # noqa: BLE001 - thread top-level; recorded as exit 1 + run.finished
            traceback.print_exc()
            state.finish(1)
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
        state.finish(exit_code)
        state.bus.publish(
            {
                "type": "run.finished",
                "run_id": state.id,
                "exit_code": exit_code,
            }
        )
        state.bus.close()
