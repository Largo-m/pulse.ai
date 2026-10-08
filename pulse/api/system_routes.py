"""Health of the daemon itself: version, protocol and the doctor checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pulse import __version__
from pulse.api.deps import workspace_path
from pulse.client.protocol import ENGINE_PROTOCOL
from pulse.config.resolved import resolve_config
from pulse.doctor.checks import run_doctor_checks
from pulse.runtimes import find_runtime
from pulse.store.paths import safe_cwd

router = APIRouter()


@router.get("/api/status")
def status() -> dict[str, Any]:
    return {
        "ok": True,
        "version": __version__,
        "service": "pulse-engine",
        "protocol": ENGINE_PROTOCOL,
    }


@router.get("/api/doctor")
def doctor() -> dict[str, Any]:
    return {
        "checks": [
            {
                "name": item.name,
                "status": item.status,
                "message": item.message,
                "detail": item.detail,
            }
            for item in run_doctor_checks()
        ]
    }


def _probe_command(workspace: str | None, runtime: str | None) -> list[str]:
    """The configured ACP command, or the named runtime's; an unknown runtime is a 404."""
    if runtime is None:
        return list(resolve_config(workspace=workspace_path(workspace)).acp_command)
    selected = find_runtime(runtime)
    if selected is None:
        raise HTTPException(status_code=404, detail=f"unknown runtime: {runtime}")
    return list(selected.acp_command)


@router.post("/api/doctor/acp-probe")
def acp_probe(workspace: str | None = None, runtime: str | None = None) -> dict[str, Any]:
    from pulse.acp.client import probe_acp_connection

    command = _probe_command(workspace, runtime)
    result = probe_acp_connection(command=command, cwd=workspace or str(safe_cwd()))
    return {
        "ok": result.success,
        "message": result.message,
        "error": result.error,
        "response_text": result.response_text,
        "available_models": result.available_models,
    }
