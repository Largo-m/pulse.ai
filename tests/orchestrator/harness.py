"""The engine wired to the in-memory fakes, the way the daemon wires the real adapters."""

from __future__ import annotations

from pathlib import Path

from pulse.domain.control import RunControl
from pulse.orchestrator.engine import EnginePorts, run_workflow
from pulse.store.workflow_defs import get_workflow
from tests.fakes import (
    FakeAgentSession,
    FakeWorkspace,
    FixedAgentProfiles,
    InMemoryRunRepository,
)


class EngineHarness:
    """One project: runs, workspace and agent profiles shared by every run started on it.

    Definitions come from the database (`make_workflow`), as tests seed them;
    everything the engine writes stays in memory.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs = InMemoryRunRepository()
        self.workspace = FakeWorkspace(root, repo=False)
        self.agents = FixedAgentProfiles()

    def run(
        self,
        session: FakeAgentSession,
        *,
        workflow_id: str,
        user_prompt: str,
        resume_run_id: str | None = None,
        run_id: str | None = None,
        control: RunControl | None = None,
        use_worktree: bool = False,
    ) -> int:
        definition = get_workflow(workflow_id)
        assert definition is not None, f"seed `{workflow_id}` with make_workflow first"
        ports = EnginePorts(
            session=session,
            stream=session.stream,
            runs=self.runs,
            workspace=self.workspace,
            agents=self.agents,
        )
        return run_workflow(
            definition=definition,
            user_prompt=user_prompt,
            ports=ports,
            use_worktree=use_worktree,
            resume_run_id=resume_run_id,
            control=control or session.control,
            run_id=run_id,
        )
