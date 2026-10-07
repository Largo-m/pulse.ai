from pathlib import Path

from pulse.config.agents import AgentConfig, WorkflowConfig
from pulse.config.global_config import (
    GlobalConfig,
    global_config_exists,
    load_global_config,
    mark_onboarding_complete,
    save_global_config,
)


def test_global_config_roundtrip(tmp_path: Path):
    config_path = tmp_path / "pulse.db"
    saved = mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="composer-2.5",
        permission_policy="ask",
        acp_test_passed=True,
        path=config_path,
    )
    assert saved == config_path
    assert global_config_exists(config_path)

    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.is_onboarded
    assert loaded.model == "composer-2.5"
    assert loaded.permission_policy == "ask"
    assert loaded.workspace_dir == tmp_path.resolve()
    assert loaded.default_agent == "cursor"
    assert "cursor" in loaded.agents
    assert "claude" in loaded.agents


def test_global_config_agents_and_workflows_roundtrip(tmp_path: Path):
    config_path = tmp_path / "pulse.db"
    config = GlobalConfig(
        version=1,
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="Auto",
        permission_policy="auto_approve",
        completed_at="2026-06-21T12:00:00+00:00",
        acp_test_passed=True,
        default_agent="cursor",
        agents={
            "cursor": AgentConfig(
                name="cursor",
                binary="agent",
                acp_command=["agent", "acp"],
                models=["Auto", "gpt-5.5"],
            ),
        },
        workflows={
            "fluxo-a": WorkflowConfig(agent="cursor", model="gpt-5.5"),
        },
    )
    save_global_config(config, config_path)

    loaded = load_global_config(config_path)

    assert loaded is not None
    assert loaded.default_agent == "cursor"
    assert loaded.agents["cursor"].models == ["Auto", "gpt-5.5"]
    assert loaded.workflows["fluxo-a"].agent == "cursor"
    assert loaded.workflows["fluxo-a"].model == "gpt-5.5"


def test_save_global_config_creates_parent(tmp_path: Path):
    config_path = tmp_path / "nested" / "pulse.db"
    config = GlobalConfig(
        version=1,
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="composer-2.5",
        permission_policy="ask",
    )
    save_global_config(config, config_path)
    assert config_path.is_file()


def test_saving_honours_pulse_db_like_loading_does(monkeypatch, tmp_path):
    """Writing to one file and reading from another trapped onboarding in a loop."""
    from pulse.config.global_config import load_global_config, mark_onboarding_complete

    monkeypatch.setenv("PULSE_DB", str(tmp_path / "outro.db"))
    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="Auto",
        permission_policy="ask",
        acp_test_passed=True,
    )

    assert load_global_config() is not None
    assert (tmp_path / "outro.db").exists()
