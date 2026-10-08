"""Gates checked before the engine opens the ACP session.

They raise for whoever started the run: the engine has one path, and the
caller decides how a refusal is shown.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.orchestrator import engine
from pulse.orchestrator.engine import UnknownWorkflow, run_workflow
from tests.conftest import make_workflow


def _resolved(tmp_path: Path):
    class Resolved:
        workspace_dir = tmp_path
        permission_policy = "ask"
        acp_command = ["agent", "acp"]
        model = "auto"
        agent_name = "cursor"

    return Resolved()


def test_an_unready_runtime_is_an_error_for_the_caller(monkeypatch, tmp_path: Path):
    from pulse.doctor.checks import CheckResult

    make_workflow("demo")
    monkeypatch.setattr(engine, "resolve_config", lambda **_kwargs: _resolved(tmp_path))
    monkeypatch.setattr(
        engine,
        "check_runtime_ready",
        lambda _runtime: CheckResult("Cursor CLI", "fail", "sem agent", "instale o Cursor CLI"),
    )
    with pytest.raises(RuntimeError, match="indisponível"):
        run_workflow(
            workflow_id="demo",
            user_prompt="x",
        )


def test_unknown_workflow_is_an_error(monkeypatch):
    """With no catalog in code, an id missing from the database does not exist."""
    with pytest.raises(UnknownWorkflow, match="desconhecido"):
        run_workflow(
            workflow_id="nao-existe",
            user_prompt="x",
        )


def test_workflow_without_steps_does_not_start(monkeypatch):
    from pulse.domain.workflow import WorkflowDef
    from pulse.store.workflow_defs import save_workflow

    save_workflow(WorkflowDef(id="vazio", label="Vazio"))
    with pytest.raises(UnknownWorkflow, match="step"):
        run_workflow(
            workflow_id="vazio",
            user_prompt="x",
        )
