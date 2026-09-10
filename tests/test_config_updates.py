from pathlib import Path

import yaml

from pulse.config.global_config import (
    load_global_config,
    mark_onboarding_complete,
    update_global_agent,
    update_global_defaults,
)
from pulse.config.project_config import init_project_config, load_project_config, update_project_defaults


def test_update_global_defaults_model(tmp_path: Path):
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

    update_global_defaults(model="gpt-5.5", path=config_path)
    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.model == "gpt-5.5"
    assert loaded.permission_policy == "ask"


def test_update_global_defaults_agent(tmp_path: Path):
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

    update_global_defaults(agent="claude", path=config_path)
    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.default_agent == "claude"


def test_update_global_agent(tmp_path: Path):
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

    update_global_agent(
        "cursor",
        models=["Auto", "gpt-5.5", "composer-2.5"],
        path=config_path,
    )
    loaded = load_global_config(config_path)
    assert loaded is not None
    assert loaded.agents["cursor"].models == ["Auto", "gpt-5.5", "composer-2.5"]


def test_update_project_defaults_model(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_defaults(tmp_path, model="composer-2.5")
    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.model == "composer-2.5"

    raw = yaml.safe_load((tmp_path / ".pulse" / "config.yaml").read_text(encoding="utf-8"))
    assert raw["defaults"]["model"] == "composer-2.5"
