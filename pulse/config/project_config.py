from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pulse.config.agents import AgentConfig, WorkflowConfig, parse_agents, parse_workflows
from pulse.config.global_config import PERMISSION_POLICIES
from pulse.config.paths import find_project_config_file, project_config_file


@dataclass(frozen=True)
class ProjectConfig:
    source_file: Path
    model: str | None = None
    permission_policy: str | None = None
    workspace: Path | None = None
    default_agent: str | None = None
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    workflows: dict[str, WorkflowConfig] = field(default_factory=dict)

    @property
    def project_root(self) -> Path:
        return self.source_file.parent.parent.resolve()


def load_project_config(start: Path | None = None) -> ProjectConfig | None:
    config_file = find_project_config_file(start)
    if config_file is None:
        return None
    return parse_project_config(config_file)


def parse_project_config(config_file: Path) -> ProjectConfig:
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raw = {}

    defaults = raw.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}
    workspace_section = raw.get("workspace")
    if not isinstance(workspace_section, dict):
        workspace_section = {}

    model = defaults.get("model")
    model = str(model) if model else None

    policy = defaults.get("permission_policy")
    if policy not in PERMISSION_POLICIES:
        policy = None

    default_agent = defaults.get("agent")
    default_agent = str(default_agent) if default_agent else None

    project_root = config_file.parent.parent
    workspace_value = workspace_section.get("root")
    workspace_path: Path | None = None
    if workspace_value:
        candidate = Path(str(workspace_value)).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        workspace_path = candidate.resolve()

    return ProjectConfig(
        source_file=config_file,
        model=model,
        permission_policy=policy,
        workspace=workspace_path,
        default_agent=default_agent,
        agents=parse_agents(raw.get("agents")),
        workflows=parse_workflows(raw.get("workflows")),
    )


def project_config_exists(start: Path | None = None) -> bool:
    return find_project_config_file(start) is not None


DEFAULT_PROJECT_WORKFLOWS: dict[str, WorkflowConfig] = {
    "new-issue": WorkflowConfig(agent="cursor", model="Auto"),
    "fix-bug": WorkflowConfig(agent="cursor", model="Auto"),
    "setup-project": WorkflowConfig(agent="claude", model="claude-opus-4.8"),
    "analyze-codebase": WorkflowConfig(agent="cursor", model="gpt-5.5"),
}

DEFAULT_PROJECT_CONFIG = """\
version: 1

defaults:
  agent: cursor
  model: claude-sonnet-4-6
  permission_policy: deny_writes

workspace:
  root: .

workflows:
  new-issue:
    agent: cursor
    model: Auto
  fix-bug:
    agent: cursor
    model: Auto
  setup-project:
    agent: claude
    model: claude-opus-4.8
  analyze-codebase:
    agent: cursor
    model: gpt-5.5
"""


def render_project_config() -> str:
    return DEFAULT_PROJECT_CONFIG


def init_project_config(root: Path) -> Path:
    target = project_config_file(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_project_config(), encoding="utf-8")
    return target


def _load_raw_project_config(root: Path) -> tuple[Path, dict]:
    config_path = find_project_config_file(root)
    if config_path is None:
        config_path = init_project_config(root)

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raw = {}
    return config_path, raw


def _write_raw_project_config(config_path: Path, raw: dict) -> Path:
    config_path.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path


def _ensure_workflows_in_raw(raw: dict) -> bool:
    workflows = raw.setdefault("workflows", {})
    if not isinstance(workflows, dict):
        workflows = {}
        raw["workflows"] = workflows

    changed = False
    for workflow_id, defaults in DEFAULT_PROJECT_WORKFLOWS.items():
        entry = workflows.get(workflow_id)
        if isinstance(entry, dict):
            continue
        workflows[workflow_id] = {
            key: value
            for key, value in (("agent", defaults.agent), ("model", defaults.model))
            if value is not None
        }
        changed = True
    return changed


def ensure_project_workflows(root: Path) -> Path:
    config_path, raw = _load_raw_project_config(root)
    if _ensure_workflows_in_raw(raw):
        return _write_raw_project_config(config_path, raw)
    return config_path


def update_project_defaults(
    root: Path,
    *,
    model: str | None = None,
    permission_policy: str | None = None,
    agent: str | None = None,
) -> Path:
    config_path, raw = _load_raw_project_config(root)

    defaults = raw.setdefault("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
        raw["defaults"] = defaults

    if model is not None:
        defaults["model"] = model
    if permission_policy is not None:
        if permission_policy not in PERMISSION_POLICIES:
            raise ValueError(f"Política inválida: {permission_policy}")
        defaults["permission_policy"] = permission_policy
    if agent is not None:
        defaults["agent"] = agent

    return _write_raw_project_config(config_path, raw)


def update_project_workflow(
    root: Path,
    workflow_id: str,
    *,
    agent: str | None = None,
    model: str | None = None,
) -> Path:
    config_path, raw = _load_raw_project_config(root)
    _ensure_workflows_in_raw(raw)

    workflows = raw["workflows"]
    entry = workflows.get(workflow_id)
    if not isinstance(entry, dict):
        entry = {}
        workflows[workflow_id] = entry

    if agent is not None:
        entry["agent"] = agent
    if model is not None:
        entry["model"] = model

    return _write_raw_project_config(config_path, raw)


def update_project_agent(
    root: Path,
    agent_name: str,
    *,
    binary: str | None = None,
    models: list[str] | None = None,
    acp_command: list[str] | None = None,
) -> Path:
    config_path, raw = _load_raw_project_config(root)

    agents = raw.setdefault("agents", {})
    if not isinstance(agents, dict):
        agents = {}
        raw["agents"] = agents

    entry = agents.get(agent_name)
    if not isinstance(entry, dict):
        entry = {}
        agents[agent_name] = entry

    if binary is not None:
        entry["binary"] = binary
        if acp_command is None and "acp_command" not in entry:
            entry["acp_command"] = [binary, "acp"]
    if models is not None:
        entry["models"] = list(models)
    if acp_command is not None:
        entry["acp_command"] = list(acp_command)
    if "binary" not in entry:
        entry["binary"] = agent_name
    if "models" not in entry:
        entry["models"] = []

    return _write_raw_project_config(config_path, raw)
