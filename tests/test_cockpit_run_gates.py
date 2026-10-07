"""Gates checked before the engine opens the ACP session."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.conftest import make_workflow

from pulse.orchestrator import engine
from pulse.orchestrator.engine import UnknownWorkflow, run_workflow
from pulse.runtime.tty import is_cockpit_stream


@dataclass
class _CockpitStream:
    cockpit: bool = True
    errors: list = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def error(self, title: str, reason: str = "") -> None:
        self.errors.append((title, reason))


def _resolved(tmp_path: Path):
    class Resolved:
        workspace_dir = tmp_path
        permission_policy = "ask"
        acp_command = ["agent", "acp"]
        model = "auto"
        agent_name = "cursor"

    return Resolved()


def test_is_cockpit_stream_detects_flag():
    assert is_cockpit_stream(_CockpitStream()) is True
    assert is_cockpit_stream(_CockpitStream(cockpit=False)) is False
    assert is_cockpit_stream(None) is False
    assert is_cockpit_stream(object()) is False


def test_cockpit_bypasses_interactive_gate(monkeypatch, tmp_path: Path):
    make_workflow("demo")
    monkeypatch.setattr(engine, "is_interactive", lambda: False)
    monkeypatch.setattr(engine, "check_runtime_ready", lambda _runtime: None)
    monkeypatch.setattr(engine, "resolve_config", lambda **_kwargs: _resolved(tmp_path))

    class _Runner:
        def bind_run(self, run_id: str, waits: object = None) -> None:
            pass

    monkeypatch.setattr(engine, "AcpSessionRunner", lambda *_a, **_k: _Runner())
    monkeypatch.setattr(engine, "_execute", lambda **_k: 0)

    assert (
        run_workflow(
            workflow_id="demo",
            user_prompt="x",
            stream=_CockpitStream(),
            render_header=False,
        )
        == 0
    )


def test_non_cockpit_still_requires_interactive(monkeypatch):
    make_workflow("demo")
    monkeypatch.setattr(engine, "is_interactive", lambda: False)
    assert run_workflow(workflow_id="demo", user_prompt="x", render_header=False) == 1


def test_cockpit_surfaces_runtime_failures(monkeypatch, tmp_path: Path):
    from pulse.doctor.checks import CheckResult

    make_workflow("demo")
    monkeypatch.setattr(engine, "is_interactive", lambda: False)
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
            stream=_CockpitStream(),
            render_header=False,
        )


def test_unknown_workflow_is_an_error(monkeypatch):
    """With no catalog in code, an id missing from the database does not exist."""
    monkeypatch.setattr(engine, "is_interactive", lambda: False)
    with pytest.raises(UnknownWorkflow, match="desconhecido"):
        run_workflow(
            workflow_id="nao-existe",
            user_prompt="x",
            stream=_CockpitStream(),
            render_header=False,
        )


def test_workflow_without_steps_does_not_start(monkeypatch):
    from pulse.store.workflow_defs import WorkflowDef, save_workflow

    save_workflow(WorkflowDef(id="vazio", label="Vazio"))
    monkeypatch.setattr(engine, "is_interactive", lambda: False)
    with pytest.raises(UnknownWorkflow, match="step"):
        run_workflow(
            workflow_id="vazio",
            user_prompt="x",
            stream=_CockpitStream(),
            render_header=False,
        )
