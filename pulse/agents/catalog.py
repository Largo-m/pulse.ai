from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    label: str
    description: str
    runtime: str = "cursor"
    model: str = "Auto"
    permission_policy: str = "ask"
    source_files: tuple[str, ...] = ()


BUNDLED_AGENTS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        id="classify",
        label="Classificar",
        description="Escolhe flow full ou quick",
        model="Auto",
        permission_policy="deny_writes",
        source_files=("quick-mode.md", "specify.md", "user-input.md"),
    ),
    AgentDefinition(
        id="specify",
        label="Specify",
        description="Escreve spec.md",
        permission_policy="deny_writes",
        source_files=("specify.md", "discuss.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="design",
        label="Design",
        description="Escreve design.md",
        permission_policy="deny_writes",
        source_files=("design.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="tasks",
        label="Tasks",
        description="Escreve tasks.md",
        permission_policy="deny_writes",
        source_files=("tasks.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="implement",
        label="Implementar",
        description="Executa tasks.md",
        model="gpt-5.5",
        permission_policy="ask",
        source_files=("implement.md", "validate.md", "coding-principles.md", "state-management.md"),
    ),
    AgentDefinition(
        id="quick-plan",
        label="Quick plan",
        description="Plano do quick mode",
        permission_policy="deny_writes",
        source_files=("quick-mode.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="quick-implement",
        label="Quick implement",
        description="Implementação do quick mode",
        model="gpt-5.5",
        source_files=("quick-mode.md", "coding-principles.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="setup-interview",
        label="Setup entrevista",
        description="Entrevista de setup do projeto",
        runtime="claude",
        model="claude-opus-4.8",
        permission_policy="deny_writes",
        source_files=("project-init.md", "roadmap.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="setup-artifacts",
        label="Setup artefatos",
        description="Gera PROJECT.md e ROADMAP.md",
        runtime="claude",
        model="claude-opus-4.8",
        permission_policy="deny_writes",
        source_files=("project-init.md", "roadmap.md", "state-management.md", "user-input.md"),
    ),
    AgentDefinition(
        id="codebase-explore",
        label="Explorar codebase",
        description="Mapeia um repositório existente",
        model="gpt-5.5",
        permission_policy="deny_writes",
        source_files=("brownfield-mapping.md", "concerns.md", "code-analysis.md", "user-input.md"),
    ),
    AgentDefinition(
        id="codebase-docs",
        label="Docs de codebase",
        description="Gera docs em .pulse/specs/codebase",
        model="gpt-5.5",
        permission_policy="deny_writes",
        source_files=("brownfield-mapping.md", "concerns.md", "code-analysis.md", "user-input.md"),
    ),
)

AGENT_BY_ID = {item.id: item for item in BUNDLED_AGENTS}

SPEC_FULL_AGENTS = ("specify", "design", "tasks", "implement")
SPEC_QUICK_AGENTS = ("quick-plan", "quick-implement")
SETUP_AGENTS = ("setup-interview", "setup-artifacts")
ANALYZE_AGENTS = ("codebase-explore", "codebase-docs")

WORKFLOW_AGENTS = {
    "spec": ("classify",),
    "setup-project": SETUP_AGENTS,
    "analyze-codebase": ANALYZE_AGENTS,
    "new-issue": SPEC_FULL_AGENTS,
    "fix-bug": SPEC_QUICK_AGENTS,
}
