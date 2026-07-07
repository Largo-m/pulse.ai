from pathlib import Path

from pulse.config.paths import PROJECT_SPECS_DIRNAME, project_specs_dir


def test_project_specs_dir(tmp_path: Path):
    assert PROJECT_SPECS_DIRNAME == ".pulse/specs"
    assert project_specs_dir(tmp_path) == tmp_path / ".pulse" / "specs"
from pulse.config.project_config import (
    init_project_config,
    load_project_config,
    parse_project_config,
    project_config_exists,
)


def _write_project_config(root: Path, body: str) -> Path:
    target = root / ".pulse" / "config.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


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

    content = path.read_text(encoding="utf-8")
    assert "agents:" not in content
