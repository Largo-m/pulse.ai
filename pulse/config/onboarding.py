"""Where a first run stands, and what finishing the setup wizard writes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pulse.config.global_config import (
    global_config_exists,
    load_global_config,
    mark_onboarding_complete,
)
from pulse.config.project_config import init_project_config, project_config_exists
from pulse.config.ready import is_pulse_ready
from pulse.runtimes import get_runtime


@dataclass(frozen=True)
class SetupState:
    configured: bool
    onboarded: bool
    ready: bool
    workspace_dir: str


def setup_state(workspace: Path) -> SetupState:
    machine = load_global_config()
    return SetupState(
        configured=global_config_exists(),
        onboarded=bool(machine and machine.is_onboarded),
        ready=is_pulse_ready(workspace),
        workspace_dir=str(machine.workspace_dir) if machine else "",
    )


def complete_onboarding(
    *,
    runtime_id: str,
    workspace: Path,
    model: str,
    permission_policy: str,
    auth_method: str,
    acp_test_passed: bool,
) -> Path:
    """Save the machine defaults the wizard collected and open the chosen workspace.

    The runtime's binary and ACP command come from its registered class, never
    from the request, so a client cannot make the daemon spawn an arbitrary argv.
    """
    runtime = get_runtime(runtime_id)
    path = mark_onboarding_complete(
        agent_binary=runtime.find_binary() or runtime.binary,
        acp_command=list(runtime.acp_command),
        auth_method=auth_method,
        workspace_dir=workspace,
        model=model,
        permission_policy=permission_policy,
        acp_test_passed=acp_test_passed,
        default_agent=runtime.id,
    )
    if not project_config_exists(workspace):
        init_project_config(workspace)
    return path
