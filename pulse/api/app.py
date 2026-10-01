from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from pulse import __version__
from pulse.config.global_config import (
    load_global_config,
    update_global_defaults,
)
from pulse.config.project_config import init_project_config, load_project_config
from pulse.config.resolved import resolve_config
from pulse.daemon.protocol import ENGINE_PROTOCOL
from pulse.daemon.runs import RunAlreadyActive, RunManager
from pulse.doctor.checks import run_doctor_checks
from pulse.history.catalog import HistoryCatalog

class StartRunBody(BaseModel):
    prompt: str = ""
    workspace: str | None = None
    #: Run anterior a retomar, do primeiro step que não fechou.
    resume_run_id: str | None = None


class PromptAnswerBody(BaseModel):
    answer: Any = None


class ConfigPatchBody(BaseModel):
    model: str | None = None
    permission_policy: str | None = None
    default_agent: str | None = None


class ProjectConfigBody(BaseModel):
    workspace: str


def _global_to_dict(config: Any) -> dict[str, Any] | None:
    if config is None:
        return None
    return {
        "version": config.version,
        "agent_binary": config.agent_binary,
        "acp_command": list(config.acp_command),
        "auth_method": config.auth_method,
        "workspace_dir": str(config.workspace_dir),
        "model": config.model,
        "permission_policy": config.permission_policy,
        "completed_at": config.completed_at,
        "acp_test_passed": config.acp_test_passed,
        "default_agent": config.default_agent,
    }


def _project_to_dict(config: Any) -> dict[str, Any] | None:
    if config is None:
        return None
    return {
        "source_file": str(config.source_file),
        "model": config.model,
        "permission_policy": config.permission_policy,
        "workspace": str(config.workspace) if config.workspace else None,
        "default_agent": config.default_agent,
    }


def _history_to_dict(item: Any) -> dict[str, Any]:
    return {
        "id": item.item_id,
        "run_id": item.run_id,
        "workflow_id": item.workflow_id,
        "workflow_label": item.workflow_label,
        "title": item.title,
        "prompt": item.prompt,
        "status": item.status.value,
        "updated_at": item.updated_at,
        "artifacts": list(item.artifacts),
        "steps": [
            {"id": step.id, "label": step.label, "status": step.status}
            for step in item.steps
        ],
    }


def create_app(manager: RunManager | None = None) -> FastAPI:
    runs = manager or RunManager()
    app = FastAPI(title="Pulse Engine", version=__version__)
    app.state.runs = runs

    @app.get("/api/status")
    def status() -> dict[str, Any]:
        return {
            "ok": True,
            "version": __version__,
            "service": "pulse-engine",
            "protocol": ENGINE_PROTOCOL,
        }

    @app.get("/api/doctor")
    def doctor() -> dict[str, Any]:
        results = run_doctor_checks()
        return {
            "checks": [
                {
                    "name": item.name,
                    "status": item.status,
                    "message": item.message,
                    "detail": item.detail,
                }
                for item in results
            ]
        }

    @app.post("/api/doctor/acp-probe")
    def acp_probe(workspace: str | None = None) -> dict[str, Any]:
        from pulse.acp.client import probe_acp_connection

        cwd = workspace or str(Path.cwd())
        ws = Path(workspace).resolve() if workspace else None
        result = probe_acp_connection(
            command=list(resolve_config(workspace=ws).acp_command),
            cwd=cwd,
        )
        return {
            "ok": result.success,
            "message": result.message,
            "error": result.error,
            "response_text": result.response_text,
        }

    @app.get("/api/config")
    def get_config() -> dict[str, Any]:
        return {
            "global": _global_to_dict(load_global_config()),
            "project": _project_to_dict(load_project_config()),
        }

    @app.get("/api/config/resolved")
    def get_resolved(workflow: str | None = None, workspace: str | None = None) -> dict[str, Any]:
        ws = Path(workspace).resolve() if workspace else None
        resolved = resolve_config(workspace=ws, workflow=workflow)
        return {
            "agent": resolved.agent_name,
            "model": resolved.model,
            "permission_policy": resolved.permission_policy,
            "workspace": str(resolved.workspace_dir),
            "acp_command": list(resolved.acp_command),
            "auth_method": resolved.auth_method,
        }

    @app.patch("/api/config/global")
    def patch_global(body: ConfigPatchBody) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if body.model is not None:
            kwargs["model"] = body.model
        if body.permission_policy is not None:
            kwargs["permission_policy"] = body.permission_policy
        if body.default_agent is not None:
            kwargs["agent"] = body.default_agent
        if kwargs:
            update_global_defaults(**kwargs)
        return {"ok": True, "global": _global_to_dict(load_global_config())}

    @app.post("/api/config/project")
    def post_project(body: ProjectConfigBody) -> dict[str, Any]:
        path = init_project_config(Path(body.workspace))
        return {"ok": True, "path": str(path)}

    @app.get("/api/workflows")
    def workflows() -> dict[str, Any]:
        return {"workflows": runs.list_workflows()}

    @app.post("/api/workflows/{workflow_id}/runs")
    def start_workflow_run(workflow_id: str, body: StartRunBody) -> dict[str, Any]:
        try:
            state = runs.start_run(
                workflow_id=workflow_id,
                prompt=body.prompt,
                workspace=body.workspace,
                resume_run_id=body.resume_run_id,
            )
        except RunAlreadyActive as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "id": state.id,
            "workflow_id": state.workflow_id,
            "status": state.status,
            "workspace": state.workspace,
        }

    @app.get("/api/runs")
    def list_runs() -> dict[str, Any]:
        return {"runs": runs.list_runs()}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        state = runs.get(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="run não encontrado")
        return {
            "id": state.id,
            "workflow_id": state.workflow_id,
            "prompt": state.prompt,
            "workspace": state.workspace,
            "status": state.status,
            "exit_code": state.exit_code,
        }

    @app.post("/api/runs/{run_id}/cancel")
    def cancel_run(run_id: str) -> dict[str, Any]:
        if not runs.cancel(run_id):
            raise HTTPException(status_code=404, detail="run não encontrado")
        return {"ok": True}

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str, after: int = 0) -> StreamingResponse:
        """O stream da run: o passado dela e depois o vivo.

        `after` pula os N primeiros eventos, para quem já tem parte do histórico.
        Sem ele, anexar entrega a run inteira desde `run.started` — é assim que o
        cockpit reabre idêntico ao que era antes de o usuário sair.
        """
        state = runs.get(run_id)
        if state is None:
            raise HTTPException(status_code=404, detail="run não encontrado")

        def event_stream():
            for event in state.bus.subscribe(after=max(0, after)):
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
                if event.get("type") == "run.finished":
                    break

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/api/prompts/{prompt_id}/answer")
    def answer_prompt(prompt_id: str, body: PromptAnswerBody) -> dict[str, Any]:
        if not runs.answer_prompt(prompt_id, body.answer):
            raise HTTPException(status_code=404, detail="prompt não encontrado")
        return {"ok": True}

    @app.get("/api/history")
    def history(workspace: str | None = None, query: str = "") -> dict[str, Any]:
        root = Path(workspace).resolve() if workspace else Path.cwd()
        catalog = HistoryCatalog(root)
        items = catalog.search(query) if query else catalog.list_items()
        return {"items": [_history_to_dict(item) for item in items]}

    @app.get("/api/history/{item_id}")
    def history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace).resolve() if workspace else Path.cwd()
        item = HistoryCatalog(root).get(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="item não encontrado")
        return _history_to_dict(item)

    @app.delete("/api/history/{item_id}")
    def delete_history_item(item_id: str, workspace: str | None = None) -> dict[str, Any]:
        root = Path(workspace).resolve() if workspace else Path.cwd()
        if not HistoryCatalog(root).delete(item_id):
            raise HTTPException(status_code=404, detail="item não encontrado")
        return {"ok": True}

    @app.exception_handler(Exception)
    async def on_error(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return app
