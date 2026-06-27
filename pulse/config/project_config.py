from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from pulse.config.agents import (
    AgentConfig,
    WorkflowConfig,
    parse_agents,
    parse_workflows,
)
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
        return self.source_file.parent.parent


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


DEFAULT_PROJECT_CONFIG = """\
version: 1

defaults:
  agent: cursor
  model: claude-sonnet-4-6
  permission_policy: deny_writes

workspace:
  root: .

agents:
  cursor:
    binary: agent
    models: [Auto, gpt-5.5]
  claude:
    binary: claude-code
    models: [claude-opus-4.8]

workflows:
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
