from pathlib import Path

from pulse.config.global_config import (
    GlobalConfig,
    global_config_exists,
    load_global_config,
    mark_onboarding_complete,
    save_global_config,
)


def test_global_config_roundtrip(tmp_path: Path):
    config_path = tmp_path / "config.toml"
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


def test_global_config_to_toml_contains_sections():
    config = GlobalConfig(
        version=1,
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="api_key",
        workspace_dir=Path("/tmp/work"),
        model="gpt-5.5",
        permission_policy="auto_approve",
        completed_at="2026-06-21T12:00:00+00:00",
        acp_test_passed=True,
    )
    toml = config.to_toml()
    assert "[agent]" in toml
    assert "[auth]" in toml
    assert "[defaults]" in toml
    assert "[onboarding]" in toml
    assert 'permission_policy = "auto_approve"' in toml


def test_save_global_config_creates_parent(tmp_path: Path):
    config_path = tmp_path / "nested" / "config.toml"
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
