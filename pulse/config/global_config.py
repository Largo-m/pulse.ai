from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pulse.config.agents import (
    DEFAULT_AGENT_NAME,
    AgentConfig,
    WorkflowConfig,
    parse_agents,
    parse_workflows,
)
from pulse.config.paths import (
    GLOBAL_CONFIG_DIR,
    GLOBAL_CONFIG_FILE,
    LEGACY_GLOBAL_CONFIG_FILE,
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


PERMISSION_POLICIES = ("ask", "auto_approve", "deny_writes")


@dataclass(frozen=True)
class GlobalConfig:
    version: int
    agent_binary: str
    acp_command: list[str]
    auth_method: str
    workspace_dir: Path
    model: str
    permission_policy: str
    completed_at: str | None = None
    acp_test_passed: bool = False
    default_agent: str = DEFAULT_AGENT_NAME
    agents: dict[str, AgentConfig] = field(default_factory=dict)
    workflows: dict[str, WorkflowConfig] = field(default_factory=dict)

    @property
    def is_onboarded(self) -> bool:
        return self.completed_at is not None

    def to_toml(self) -> str:
        acp = ", ".join(f'"{part}"' for part in self.acp_command)
        completed = f'"{self.completed_at}"' if self.completed_at else "null"
        acp_passed = "true" if self.acp_test_passed else "false"
        workspace = str(self.workspace_dir).replace("\\", "\\\\")
        toml = (
            f'version = {self.version}\n\n'
            f"[agent]\n"
            f'binary = "{self.agent_binary}"\n'
            f"acp_command = [{acp}]\n\n"
            f'[auth]\n'
            f'method = "{self.auth_method}"\n\n'
            f"[defaults]\n"
            f'agent = "{self.default_agent}"\n'
            f'workspace_dir = "{workspace}"\n'
            f'model = "{self.model}"\n'
            f'permission_policy = "{self.permission_policy}"\n\n'
            f"[onboarding]\n"
            f"completed_at = {completed}\n"
            f"acp_test_passed = {acp_passed}\n"
        )
        toml += self._agents_toml()
        toml += self._workflows_toml()
        return toml

    def _agents_toml(self) -> str:
        blocks = ""
        for name, agent in self.agents.items():
            command = ", ".join(f'"{part}"' for part in agent.acp_command)
            models = ", ".join(f'"{model}"' for model in agent.models)
            blocks += (
                f"\n[agents.{name}]\n"
                f'binary = "{agent.binary}"\n'
                f"acp_command = [{command}]\n"
                f"models = [{models}]\n"
            )
        return blocks

    def _workflows_toml(self) -> str:
        blocks = ""
        for workflow_id, workflow in self.workflows.items():
            blocks += f"\n[workflows.{workflow_id}]\n"
            if workflow.agent:
                blocks += f'agent = "{workflow.agent}"\n'
            if workflow.model:
                blocks += f'model = "{workflow.model}"\n'
        return blocks


def migrate_legacy_global_config() -> bool:
    if GLOBAL_CONFIG_FILE.exists():
        return False
    if not LEGACY_GLOBAL_CONFIG_FILE.exists():
        return False
    GLOBAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEGACY_GLOBAL_CONFIG_FILE, GLOBAL_CONFIG_FILE)
    return True


def global_config_exists(path: Path | None = None) -> bool:
    if path is None:
        migrate_legacy_global_config()
        return GLOBAL_CONFIG_FILE.is_file()
    return path.is_file()


def load_global_config(path: Path | None = None) -> GlobalConfig | None:
    if path is None:
        migrate_legacy_global_config()
    config_path = path or GLOBAL_CONFIG_FILE
    if not config_path.is_file():
        return None

    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    agent = data.get("agent", {})
    auth = data.get("auth", {})
    defaults = data.get("defaults", {})
    onboarding = data.get("onboarding", {})

    policy = defaults.get("permission_policy", "ask")
    if policy not in PERMISSION_POLICIES:
        policy = "ask"

    return GlobalConfig(
        version=int(data.get("version", 1)),
        agent_binary=str(agent.get("binary", "agent")),
        acp_command=[str(part) for part in agent.get("acp_command", ["agent", "acp"])],
        auth_method=str(auth.get("method", "cursor_login")),
        workspace_dir=Path(str(defaults.get("workspace_dir", Path.home()))).expanduser(),
        model=str(defaults.get("model", "auto")),
        permission_policy=policy,
        completed_at=onboarding.get("completed_at"),
        acp_test_passed=bool(onboarding.get("acp_test_passed", False)),
        default_agent=str(defaults.get("agent", DEFAULT_AGENT_NAME)),
        agents=parse_agents(data.get("agents")),
        workflows=parse_workflows(data.get("workflows")),
    )


def save_global_config(config: GlobalConfig, path: Path | None = None) -> Path:
    config_path = path or GLOBAL_CONFIG_FILE
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config.to_toml(), encoding="utf-8")
    return config_path


def mark_onboarding_complete(
    *,
    agent_binary: str,
    acp_command: list[str],
    auth_method: str,
    workspace_dir: Path,
    model: str,
    permission_policy: str,
    acp_test_passed: bool,
    path: Path | None = None,
) -> Path:
    config = GlobalConfig(
        version=1,
        agent_binary=agent_binary,
        acp_command=acp_command,
        auth_method=auth_method,
        workspace_dir=workspace_dir.expanduser().resolve(),
        model=model,
        permission_policy=permission_policy,
        completed_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        acp_test_passed=acp_test_passed,
    )
    return save_global_config(config, path)
