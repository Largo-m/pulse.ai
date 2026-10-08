"""Refusals before the first step: they raise for the caller and spend no agent session."""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.domain.ports import WorkspaceError
from pulse.domain.workflow import WorkflowDef
from pulse.orchestrator.engine import EmptyWorkflow, EnginePorts, run_workflow
from pulse.store.workflow_defs import save_workflow
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession, FakeWorkspace
from tests.orchestrator.harness import EngineHarness


class _WorktreeThatWillNotOpen(FakeWorkspace):
    def add_worktree(self, run_id: str, branch: str) -> tuple[Path, str]:
        raise WorkspaceError("disco cheio")


def test_a_workflow_without_steps_does_not_start(tmp_path: Path):
    save_workflow(WorkflowDef(id="vazio", label="Vazio"))
    session = FakeAgentSession([])

    with pytest.raises(EmptyWorkflow, match="step"):
        EngineHarness(tmp_path).run(session, workflow_id="vazio", user_prompt="x")

    assert session.opened_in is None


def test_a_worktree_that_will_not_open_stops_the_run_before_the_agent(tmp_path: Path):
    """Better not to start than to start the agent in the wrong directory."""
    make_workflow("demo")
    harness = EngineHarness(tmp_path)
    harness.workspace = _WorktreeThatWillNotOpen(tmp_path, repo=True)
    session = FakeAgentSession([])

    with pytest.raises(RuntimeError, match="worktree desta run: disco cheio"):
        harness.run(session, workflow_id="demo", user_prompt="x", use_worktree=True)

    assert session.opened_in is None
    assert session.stream.contexts == []


def test_the_session_opens_where_the_run_works(tmp_path: Path):
    """The agent's cwd is the worktree, which only exists once the run has one."""
    make_workflow("demo")
    harness = EngineHarness(tmp_path)
    harness.workspace = FakeWorkspace(tmp_path, repo=True)
    session = FakeAgentSession([])

    harness.run(session, workflow_id="demo", user_prompt="x", use_worktree=True)

    worktree = tmp_path.parent / "worktrees" / harness.runs.only().id
    assert session.opened_in == worktree
    assert session.stream.contexts == [(str(worktree), harness.runs.only().branch)]
    assert session.closed is True


def test_a_crash_mid_run_is_recorded_on_the_run_and_raised(tmp_path: Path):
    """The daemon reports the error; the run must not stay `running` in history."""
    make_workflow("demo")
    harness = EngineHarness(tmp_path)

    class _AgentThatWillNotStart(FakeAgentSession):
        def open(self, cwd: Path) -> None:
            raise OSError("agente não encontrado")

    with pytest.raises(OSError, match="agente não encontrado"):
        harness.run(_AgentThatWillNotStart([]), workflow_id="demo", user_prompt="x")

    assert harness.runs.only().status == "failed"


def test_the_engine_takes_its_ports_as_one_value():
    """Every effect goes through `EnginePorts`; a new one is a field there, not a global."""
    import inspect

    assert inspect.signature(run_workflow).parameters["ports"].annotation == "EnginePorts"
    assert set(EnginePorts.__dataclass_fields__) == {
        "session",
        "stream",
        "runs",
        "workspace",
        "agents",
    }
