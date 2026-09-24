from pathlib import Path

from pulse.config.paths import (
    PROJECT_SPECS_DIRNAME,
    find_project_config_file,
    project_specs_dir,
)
from pulse.config.project_config import (
    ensure_project_workflows,
    init_project_config,
    load_project_config,
    project_config_exists,
    update_project_agent,
    update_project_defaults,
)
from pulse.store.db import connect, default_db_path


def test_project_specs_dir(tmp_path: Path):
    assert PROJECT_SPECS_DIRNAME == ".pulse/specs"
    assert project_specs_dir(tmp_path) == tmp_path / ".pulse" / "specs"


def test_load_project_config_reads_overrides(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_defaults(
        tmp_path,
        model="claude-sonnet-4-6",
        permission_policy="deny_writes",
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert config.model == "claude-sonnet-4-6"
    assert config.permission_policy == "deny_writes"
    assert config.project_root == tmp_path.resolve()


def test_find_project_config_walks_up_from_subdir(tmp_path: Path):
    init_project_config(tmp_path)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    found = find_project_config_file(nested)

    assert found == tmp_path.resolve()


def test_invalid_permission_policy_is_ignored(tmp_path: Path):
    init_project_config(tmp_path)
    config = load_project_config(tmp_path)
    assert config is not None
    connection = connect(default_db_path())
    connection.execute(
        "UPDATE project_settings SET permission_policy = ? WHERE project_id = ?",
        ("nonsense", config.project_id),
    )
    connection.commit()
    connection.close()

    loaded = load_project_config(tmp_path)

    assert loaded is not None
    assert loaded.permission_policy is None


def test_workspace_relative_is_resolved_against_project_root(tmp_path: Path):
    init_project_config(tmp_path)
    config = load_project_config(tmp_path)
    assert config is not None
    connection = connect(default_db_path())
    connection.execute(
        "UPDATE project_settings SET workspace_root = ? WHERE project_id = ?",
        ("subdir", config.project_id),
    )
    connection.commit()
    connection.close()

    loaded = load_project_config(tmp_path)

    assert loaded is not None
    assert loaded.workspace == (tmp_path / "subdir").resolve()


def test_no_project_config_returns_none(tmp_path: Path):
    assert load_project_config(tmp_path) is None
    assert project_config_exists(tmp_path) is False


def test_load_project_config_parses_workflows(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_defaults(tmp_path, agent="claude")

    config = load_project_config(tmp_path)

    assert config is not None
    assert config.default_agent == "claude"
    assert config.workflows["setup-project"].agent == "claude"
    assert config.workflows["setup-project"].model == "claude-opus-4.8"


def test_load_project_config_parses_agents(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_agent(
        tmp_path,
        "cursor",
        binary="agent",
        models=["Auto", "gpt-5.5"],
    )
    update_project_agent(
        tmp_path,
        "local",
        binary="my-agent",
        acp_command=["my-agent", "acp"],
        models=["fast"],
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert set(config.agents) == {"cursor", "local"}
    assert config.agents["cursor"].binary == "agent"
    assert config.agents["cursor"].models == ["Auto", "gpt-5.5"]
    assert config.agents["local"].acp_command == ["my-agent", "acp"]


def test_init_project_config_scaffolds_default_template(tmp_path: Path):
    path = init_project_config(tmp_path)

    assert path == tmp_path.resolve()
    config = load_project_config(tmp_path)
    assert config is not None
    assert config.default_agent == "cursor"
    assert config.model == "claude-sonnet-4-6"
    assert config.permission_policy == "deny_writes"
    assert config.workflows["setup-project"].agent == "claude"
    assert config.workflows["setup-project"].model == "claude-opus-4.8"
    assert config.workflows["analyze-codebase"].agent == "cursor"
    assert config.workflows["analyze-codebase"].model == "gpt-5.5"
    assert config.workflows["spec"].agent == "cursor"
    assert config.workflows["spec"].model == "Auto"
    assert "new-issue" not in config.workflows
    assert "fix-bug" not in config.workflows
    assert not (tmp_path / ".pulse" / "config.yaml").exists()


def test_ensure_project_workflows_adds_missing_entries(tmp_path: Path):
    init_project_config(tmp_path)
    config = load_project_config(tmp_path)
    assert config is not None
    connection = connect(default_db_path())
    connection.execute(
        "DELETE FROM project_workflows WHERE project_id = ? AND workflow_id = ?",
        (config.project_id, "spec"),
    )
    connection.commit()
    connection.close()

    path = ensure_project_workflows(tmp_path)
    loaded = load_project_config(tmp_path)

    assert path == find_project_config_file(tmp_path)
    assert loaded is not None
    assert loaded.workflows["setup-project"].agent == "claude"
    assert loaded.workflows["analyze-codebase"].agent == "cursor"
    assert loaded.workflows["spec"].agent == "cursor"
    assert loaded.workflows["spec"].model == "Auto"


def test_update_project_defaults_agent(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_defaults(tmp_path, agent="claude")
    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.default_agent == "claude"


def test_update_project_agent(tmp_path: Path):
    init_project_config(tmp_path)
    update_project_agent(
        tmp_path,
        "custom",
        binary="custom-bin",
        models=["m1", "m2"],
    )
    loaded = load_project_config(tmp_path)
    assert loaded is not None
    assert loaded.agents["custom"].binary == "custom-bin"
    assert loaded.agents["custom"].models == ["m1", "m2"]
    assert loaded.agents["custom"].acp_command == ["custom-bin", "acp"]
