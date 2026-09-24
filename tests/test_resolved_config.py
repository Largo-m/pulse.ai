from pathlib import Path

import pulse.config.resolved as resolved_module
from pulse.config.agents import AgentConfig, WorkflowConfig
from pulse.config.global_config import GlobalConfig
from pulse.config.project_config import (
    init_project_config,
    load_project_config,
    update_project_agent,
    update_project_defaults,
    update_project_workflow,
)
from pulse.config.resolved import resolve_config
from pulse.store.db import connect, default_db_path


def _global(**overrides) -> GlobalConfig:
    base = dict(
        version=1,
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=Path("/tmp/global"),
        model="global-model",
        permission_policy="auto_approve",
        completed_at="2026-06-21T12:00:00+00:00",
        acp_test_passed=True,
    )
    base.update(overrides)
    return GlobalConfig(**base)


def test_defaults_when_no_config(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: None)

    resolved = resolve_config(tmp_path)

    assert resolved.model == "auto"
    assert resolved.permission_policy == "ask"
    assert resolved.sources["model"] == "default"
    assert resolved.workspace_dir == tmp_path.resolve()
    assert resolved.sources["workspace_dir"] == "cwd"


def test_global_used_when_no_project(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: _global())

    resolved = resolve_config(tmp_path)

    assert resolved.model == "global-model"
    assert resolved.permission_policy == "auto_approve"
    assert resolved.sources["model"] == "global.default"
    assert resolved.sources["permission_policy"] == "global"


def test_project_overrides_global(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: _global())
    init_project_config(tmp_path)
    update_project_defaults(
        tmp_path,
        model="project-model",
        permission_policy="deny_writes",
    )

    resolved = resolve_config(tmp_path)

    assert resolved.model == "project-model"
    assert resolved.permission_policy == "deny_writes"
    assert resolved.sources["model"] == "project.default"
    assert resolved.sources["permission_policy"] == "project"
    assert resolved.sources["workspace_dir"] == "project_root"
    assert resolved.workspace_dir == tmp_path.resolve()


def test_partial_project_override_keeps_global(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: _global())
    init_project_config(tmp_path)
    config = load_project_config(tmp_path)
    assert config is not None
    connection = connect(default_db_path())
    connection.execute(
        "UPDATE project_settings SET model = ?, permission_policy = NULL WHERE project_id = ?",
        ("only-model", config.project_id),
    )
    connection.commit()
    connection.close()

    resolved = resolve_config(tmp_path)

    assert resolved.model == "only-model"
    assert resolved.sources["model"] == "project.default"
    assert resolved.permission_policy == "auto_approve"
    assert resolved.sources["permission_policy"] == "global"


def test_legacy_global_agent_used_as_default(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        resolved_module,
        "load_global_config",
        lambda: _global(agent_binary="legacy-agent", acp_command=["legacy-agent", "acp"]),
    )

    resolved = resolve_config(tmp_path)

    assert resolved.agent_name == "default"
    assert resolved.agent_binary == "legacy-agent"
    assert resolved.acp_command == ["legacy-agent", "acp"]


def test_global_workflow_selects_agent_and_model(monkeypatch, tmp_path: Path):
    cfg = _global(
        agents={
            "cursor": AgentConfig(
                name="cursor",
                binary="agent",
                acp_command=["agent", "acp"],
                models=["Auto"],
            ),
            "claude": AgentConfig(
                name="claude",
                binary="claude-code",
                acp_command=["claude-code", "acp"],
                models=["claude-opus-4.8"],
            ),
        },
        workflows={
            "setup-project": WorkflowConfig(agent="claude", model="claude-opus-4.8"),
        },
        default_agent="cursor",
    )
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: cfg)

    resolved = resolve_config(tmp_path, workflow="setup-project")

    assert resolved.agent_name == "claude"
    assert resolved.agent_binary == "claude-code"
    assert resolved.acp_command == ["claude-code", "acp"]
    assert resolved.model == "claude-opus-4.8"
    assert resolved.sources["agent"] == "global.workflow"
    assert resolved.sources["model"] == "global.workflow"


def test_global_workflow_falls_back_to_default_agent(monkeypatch, tmp_path: Path):
    cfg = _global(
        agents={
            "cursor": AgentConfig(
                name="cursor",
                binary="agent",
                acp_command=["agent", "acp"],
                models=["Auto"],
            ),
        },
        default_agent="cursor",
    )
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: cfg)

    resolved = resolve_config(tmp_path, workflow="analyze-codebase")

    assert resolved.agent_name == "cursor"
    assert resolved.sources["agent"] == "global.default"


def test_project_workflow_overrides_global_workflow(monkeypatch, tmp_path: Path):
    cfg = _global(
        agents={
            "cursor": AgentConfig(
                name="cursor",
                binary="agent",
                acp_command=["agent", "acp"],
                models=["Auto"],
            ),
            "claude": AgentConfig(
                name="claude",
                binary="claude-code",
                acp_command=["claude-code", "acp"],
                models=["claude-opus-4.8"],
            ),
        },
        workflows={"setup-project": WorkflowConfig(agent="cursor", model="Auto")},
        default_agent="cursor",
    )
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: cfg)
    init_project_config(tmp_path)
    update_project_workflow(
        tmp_path,
        "setup-project",
        agent="claude",
        model="claude-opus-4.8",
    )

    resolved = resolve_config(tmp_path, workflow="setup-project")

    assert resolved.agent_name == "claude"
    assert resolved.model == "claude-opus-4.8"
    assert resolved.sources["agent"] == "project.workflow"
    assert resolved.sources["model"] == "project.workflow"


def test_project_agents_override_and_extend_global(monkeypatch, tmp_path: Path):
    cfg = _global(
        agents={
            "cursor": AgentConfig(
                name="cursor",
                binary="agent",
                acp_command=["agent", "acp"],
                models=["Auto"],
            ),
        },
        default_agent="cursor",
    )
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: cfg)
    init_project_config(tmp_path)
    update_project_defaults(tmp_path, agent="local")
    update_project_agent(
        tmp_path,
        "cursor",
        binary="agent-local",
        models=["LocalAuto"],
    )
    update_project_agent(
        tmp_path,
        "local",
        binary="my-agent",
        models=["fast"],
    )

    resolved = resolve_config(tmp_path)

    assert resolved.agent_name == "local"
    assert resolved.agent_binary == "my-agent"
    assert resolved.sources["agent"] == "project.default"
    assert resolved.agents["cursor"].binary == "agent-local"
    assert resolved.agents["cursor"].models == ["LocalAuto"]
    assert "local" in resolved.agents


def test_workspace_argument_wins(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(resolved_module, "load_global_config", lambda: _global())
    init_project_config(tmp_path)
    explicit = tmp_path / "explicit"
    explicit.mkdir()

    resolved = resolve_config(tmp_path, workspace=explicit)

    assert resolved.workspace_dir == explicit.resolve()
    assert resolved.sources["workspace_dir"] == "argument"


def test_pulse_agent_model_comes_from_workspace_project(monkeypatch, tmp_path: Path):
    from pulse.store.agent_settings import upsert_agent_settings

    monkeypatch.setattr(resolved_module, "load_global_config", lambda: _global())
    project = tmp_path / "project"
    project.mkdir()
    daemon_cwd = tmp_path / "daemon"
    daemon_cwd.mkdir()
    init_project_config(project)
    loaded = load_project_config(project)
    assert loaded is not None
    upsert_agent_settings(loaded.project_id, "implement", model="Auto")

    resolved = resolve_config(daemon_cwd, workspace=project, pulse_agent="implement")

    assert resolved.model == "Auto"
    assert resolved.sources["model"] == "agent.settings"
