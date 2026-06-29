from pathlib import Path

from pulse.config.global_config import load_global_config, mark_onboarding_complete, update_global_workflow
from pulse.config.project_config import init_project_config, update_project_workflow


def test_update_global_workflow(tmp_path: Path):
    config_path = tmp_path / "config.toml"
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
        "setup-project",
        agent="claude",
        model="claude-opus-4.8",
        path=config_path,
    )
    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.workflows["setup-project"].agent == "claude"
    assert loaded.workflows["setup-project"].model == "claude-opus-4.8"


def test_update_project_workflow(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_workflow(
        tmp_path,
        "analyze-codebase",
        agent="cursor",
        model="gpt-5.5",
    )
    from pulse.config.project_config import load_project_config

    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.workflows["analyze-codebase"].agent == "cursor"
    assert loaded.workflows["analyze-codebase"].model == "gpt-5.5"
