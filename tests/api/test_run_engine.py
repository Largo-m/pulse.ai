"""`run_engine`: the daemon is the one place that knows which adapter stands behind each port.

The checks that need config, the database or the runtime run here, before the
engine spends a session; the engine receives finished ports and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config.agent_profiles import ConfiguredAgentProfiles
from pulse.daemon import runs as runs_module
from pulse.daemon.runs import UnknownWorkflow, run_engine
from pulse.doctor.checks import CheckResult
from pulse.domain.control import RunControl
from pulse.domain.ports import NullPromptPort, NullStreamSink
from pulse.store.runs import SqliteRunRepository
from pulse.vcs.workspace import GitWorkspace
from tests.conftest import make_workflow


def _start(tmp_path: Path, *, stream=None, control=None, workflow_id: str = "demo") -> int:
    return run_engine(
        workflow_id=workflow_id,
        user_prompt="x",
        workspace=tmp_path,
        stream=stream or NullStreamSink(),
        prompt_handler=NullPromptPort(),
        resume_run_id=None,
        control=control or RunControl(),
        run_id="run-1",
    )


@pytest.fixture
def ready(monkeypatch):
    """A machine whose runtime passes the doctor; CI has no agent CLI installed."""
    monkeypatch.setattr(runs_module, "check_runtime_ready", lambda _runtime: None)


def test_an_unknown_workflow_does_not_exist():
    """With no catalog in code, an id missing from the database does not exist."""
    with pytest.raises(UnknownWorkflow, match="^unknown workflow: nao-existe$"):
        _start(Path("/tmp"), workflow_id="nao-existe")  # noqa: S108 - never touched: refused first


def test_an_unready_runtime_refuses_the_run_before_any_session(monkeypatch, tmp_path: Path):
    make_workflow("demo")
    monkeypatch.setattr(
        runs_module,
        "check_runtime_ready",
        lambda _runtime: CheckResult("Cursor CLI", "fail", "sem agent", "instale o Cursor CLI"),
    )
    monkeypatch.setattr(
        runs_module,
        "run_workflow",
        lambda **_kwargs: pytest.fail("the engine must not start"),
    )

    with pytest.raises(RuntimeError, match=r"` unavailable: sem agent\. instale o Cursor CLI$"):
        _start(tmp_path)


@pytest.mark.usefixtures("ready")
def test_the_engine_gets_the_production_adapters(monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um")])
    seen: dict = {}
    monkeypatch.setattr(runs_module, "run_workflow", lambda **kwargs: seen.update(kwargs) or 0)
    stream = NullStreamSink()
    control = RunControl()

    assert _start(tmp_path, stream=stream, control=control) == 0

    ports = seen["ports"]
    assert isinstance(ports.session, AcpSessionRunner)
    assert isinstance(ports.runs, SqliteRunRepository)
    assert isinstance(ports.workspace, GitWorkspace)
    assert isinstance(ports.agents, ConfiguredAgentProfiles)
    assert ports.stream is stream
    assert ports.session.control is control, "the stop switch the API flips reaches the agent"
    assert ports.workspace.root == tmp_path.resolve()
    assert seen["definition"].id == "demo"
    assert seen["control"] is control
    assert (seen["run_id"], seen["use_worktree"]) == ("run-1", False)
