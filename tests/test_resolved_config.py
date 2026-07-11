from pathlib import Path

import pulse.config.resolved as resolved_module
from pulse.config.agents import AgentConfig, WorkflowConfig
from pulse.config.global_config import GlobalConfig
from pulse.config.resolved import resolve_config


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


def _write_project_config(root: Path, body: str) -> None:
    target = root / ".pulse" / "config.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


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
    _write_project_config(
        tmp_path,
        "version: 1\ndefaults:\n  model: project-model\n  permission_policy: deny_writes\n",
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
    _write_project_config(tmp_path, "version: 1\ndefaults:\n  model: only-model\n")

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
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "workflows:\n"
        "  setup-project:\n"
        "    agent: claude\n"
        "    model: claude-opus-4.8\n",
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
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "defaults:\n"
        "  agent: local\n"
        "agents:\n"
        "  cursor:\n"
        "    binary: agent-local\n"
        "    models: [LocalAuto]\n"
        "  local:\n"
        "    binary: my-agent\n"
        "    models: [fast]\n",
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
    _write_project_config(tmp_path, "version: 1\nworkspace:\n  root: sub\n")
    explicit = tmp_path / "explicit"
    explicit.mkdir()

    resolved = resolve_config(tmp_path, workspace=explicit)

    assert resolved.workspace_dir == explicit.resolve()
    assert resolved.sources["workspace_dir"] == "argument"
