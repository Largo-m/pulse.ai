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
    parse_project_config,
    project_config_exists,
    update_project_agent,
    update_project_defaults,
)


def _write_project_config(root: Path, body: str) -> Path:
    target = root / ".pulse" / "config.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_project_specs_dir(tmp_path: Path):
    assert PROJECT_SPECS_DIRNAME == ".pulse/specs"
    assert project_specs_dir(tmp_path) == tmp_path / ".pulse" / "specs"


def test_load_project_config_reads_overrides(tmp_path: Path):
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "defaults:\n"
        "  model: claude-sonnet-4-6\n"
        "  permission_policy: deny_writes\n",
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert config.model == "claude-sonnet-4-6"
    assert config.permission_policy == "deny_writes"
    assert config.project_root == tmp_path.resolve()


def test_find_project_config_walks_up_from_subdir(tmp_path: Path):
    _write_project_config(tmp_path, "version: 1\ndefaults:\n  model: gpt-5.5\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    found = find_project_config_file(nested)

    assert found == (tmp_path / ".pulse" / "config.yaml").resolve()


def test_invalid_permission_policy_is_ignored(tmp_path: Path):
    config_file = _write_project_config(
        tmp_path,
        "version: 1\ndefaults:\n  permission_policy: nonsense\n",
    )

    config = parse_project_config(config_file)

    assert config.permission_policy is None


def test_workspace_relative_is_resolved_against_project_root(tmp_path: Path):
    _write_project_config(
        tmp_path,
        "version: 1\nworkspace:\n  root: subdir\n",
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert config.workspace == (tmp_path / "subdir").resolve()


def test_no_project_config_returns_none(tmp_path: Path):
    assert load_project_config(tmp_path) is None
    assert project_config_exists(tmp_path) is False


def test_load_project_config_parses_workflows(tmp_path: Path):
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "defaults:\n"
        "  agent: claude\n"
        "workflows:\n"
        "  setup-project:\n"
        "    agent: claude\n"
        "    model: claude-opus-4.8\n",
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert config.default_agent == "claude"
    assert config.workflows["setup-project"].agent == "claude"
    assert config.workflows["setup-project"].model == "claude-opus-4.8"


def test_load_project_config_parses_agents(tmp_path: Path):
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "agents:\n"
        "  cursor:\n"
        "    binary: agent\n"
        "    models: [Auto, gpt-5.5]\n"
        "  local:\n"
        "    binary: my-agent\n"
        "    acp_command: [my-agent, acp]\n"
        "    models: [fast]\n",
    )

    config = load_project_config(tmp_path)

    assert config is not None
    assert set(config.agents) == {"cursor", "local"}
    assert config.agents["cursor"].binary == "agent"
    assert config.agents["cursor"].models == ["Auto", "gpt-5.5"]
    assert config.agents["local"].acp_command == ["my-agent", "acp"]


def test_init_project_config_scaffolds_default_template(tmp_path: Path):
    path = init_project_config(tmp_path)

    assert path.is_file()
    config = load_project_config(tmp_path)
    assert config is not None
    assert config.default_agent == "cursor"
    assert config.model == "claude-sonnet-4-6"
    assert config.permission_policy == "deny_writes"
    assert config.workflows["setup-project"].agent == "claude"
    assert config.workflows["setup-project"].model == "claude-opus-4.8"
    assert config.workflows["analyze-codebase"].agent == "cursor"
    assert config.workflows["analyze-codebase"].model == "gpt-5.5"
    assert config.workflows["new-issue"].agent == "cursor"
    assert config.workflows["new-issue"].model == "Auto"
    assert config.workflows["fix-bug"].agent == "cursor"
    assert config.workflows["fix-bug"].model == "Auto"

    content = path.read_text(encoding="utf-8")
    assert "agents:" not in content


def test_ensure_project_workflows_adds_missing_entries(tmp_path: Path):
    _write_project_config(
        tmp_path,
        "version: 1\n"
        "defaults:\n"
        "  agent: cursor\n"
        "  model: Auto\n"
        "  permission_policy: deny_writes\n"
        "workspace:\n"
        "  root: .\n"
        "workflows:\n"
        "  setup-project:\n"
        "    agent: cursor\n"
        "    model: Auto\n"
        "  analyze-codebase:\n"
        "    agent: cursor\n"
        "    model: Auto\n",
    )

    path = ensure_project_workflows(tmp_path)
    loaded = load_project_config(tmp_path)

    assert path == find_project_config_file(tmp_path)
    assert loaded is not None
    assert loaded.workflows["setup-project"].agent == "cursor"
    assert loaded.workflows["setup-project"].model == "Auto"
    assert loaded.workflows["analyze-codebase"].agent == "cursor"
    assert loaded.workflows["analyze-codebase"].model == "Auto"
    assert loaded.workflows["new-issue"].agent == "cursor"
    assert loaded.workflows["new-issue"].model == "Auto"
    assert loaded.workflows["fix-bug"].agent == "cursor"
    assert loaded.workflows["fix-bug"].model == "Auto"


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
