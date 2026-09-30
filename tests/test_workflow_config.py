from pathlib import Path

from pulse.config.global_config import load_global_config, mark_onboarding_complete, update_global_workflow
from pulse.config.project_config import init_project_config, load_project_config, update_project_workflow


def test_update_global_workflow(tmp_path: Path):
    config_path = tmp_path / "pulse.db"
    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="Auto",
        permission_policy="ask",
        acp_test_passed=True,
        path=config_path,
    )

    update_global_workflow(
        "fluxo-a",
        agent="claude",
        model="claude-opus-4.8",
        path=config_path,
    )
    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.workflows["fluxo-a"].agent == "claude"
    assert loaded.workflows["fluxo-a"].model == "claude-opus-4.8"


def test_update_project_workflow(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_workflow(
        tmp_path,
        "fluxo-b",
        agent="cursor",
        model="gpt-5.5",
    )
    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.workflows["fluxo-b"].agent == "cursor"
    assert loaded.workflows["fluxo-b"].model == "gpt-5.5"
