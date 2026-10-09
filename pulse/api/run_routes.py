"""Workflows, runs and the questions a run is waiting on."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pulse.api.deps import Runs
from pulse.daemon.events import EventBus
from pulse.daemon.runs import DaemonShuttingDown, RunAlreadyActive, RunManager, RunState

router = APIRouter()


class StartRunBody(BaseModel):
    prompt: str = ""
    workspace: str | None = None
    resume_run_id: str | None = None


class PromptAnswerBody(BaseModel):
    answer: Any = None


def _known_run(runs: RunManager, run_id: str) -> RunState:
    state = runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="run not found")
    return state


def _sse(bus: EventBus, after: int) -> Iterator[str]:
    for event in bus.subscribe(after=max(0, after)):
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if event.get("type") == "run.finished":
            break


@router.get("/api/workflows")
def workflows(runs: Runs) -> dict[str, Any]:
    return {"workflows": runs.list_workflows()}


@router.post("/api/workflows/{workflow_id}/runs")
def start_workflow_run(workflow_id: str, body: StartRunBody, runs: Runs) -> dict[str, Any]:
    try:
        state = runs.start_run(
            workflow_id=workflow_id,
            prompt=body.prompt,
            workspace=body.workspace,
            resume_run_id=body.resume_run_id,
        )
    except RunAlreadyActive as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except DaemonShuttingDown as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        "id": state.id,
        "workflow_id": state.workflow_id,
        "status": state.status,
        "workspace": state.workspace,
    }


@router.get("/api/runs")
def list_runs(runs: Runs) -> dict[str, Any]:
    return {"runs": runs.list_runs()}


@router.get("/api/runs/{run_id}")
def get_run(run_id: str, runs: Runs) -> dict[str, Any]:
    state = _known_run(runs, run_id)
    return {
        "id": state.id,
        "workflow_id": state.workflow_id,
        "prompt": state.prompt,
        "workspace": state.workspace,
        "status": state.status,
        "exit_code": state.exit_code,
    }


@router.post("/api/runs/{run_id}/cancel")
def cancel_run(run_id: str, runs: Runs) -> dict[str, Any]:
    if not runs.cancel(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return {"ok": True}


@router.get("/api/runs/{run_id}/events")
async def run_events(run_id: str, runs: Runs, after: int = 0) -> StreamingResponse:
    """The run stream: its past events, then live ones.

    `after` skips the first N events for clients that already have part of
    the history. Without it, attaching replays the whole run from
    `run.started`, so the cockpit reopens exactly as it was.
    """
    state = _known_run(runs, run_id)
    return StreamingResponse(_sse(state.bus, after), media_type="text/event-stream")


@router.post("/api/prompts/{prompt_id}/answer")
def answer_prompt(prompt_id: str, body: PromptAnswerBody, runs: Runs) -> dict[str, Any]:
    if not runs.answer_prompt(prompt_id, body.answer):
        raise HTTPException(status_code=404, detail="prompt not found")
    return {"ok": True}
