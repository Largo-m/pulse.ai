"""Factory configuration: the rows Pulse ships knowing how to run.

Not a code catalog: nothing here is read during a run; the engine
([pulse.orchestrator.engine]) only knows `workflow_defs`, `workflow_steps` and
`agent_defs`. This package runs once on first DB open, converts the factory
`.md` files into rows, and gets out of the way.

The `.md` playbooks stay as files so they can be reviewed in diffs. The DB
stores resolved text: `<!-- include: name -->` directives from `shared/` are
expanded at seed time so each row is self-contained.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

INCLUDE = re.compile(r"^[ \t]*<!--[ \t]*include:[ \t]*([a-z0-9-]+)[ \t]*-->[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class FactoryStep:
    agent_id: str
    label: str
    requires_approval: bool
    fan_out: bool = False
    step_id: str = ""
    repeat_from: str = ""
    repeat_max: int = 0
    phase: str = ""

    def id(self) -> str:
        return self.step_id or self.agent_id


@dataclass(frozen=True)
class FactoryWorkflow:
    id: str
    label: str
    description: str
    steps: tuple[FactoryStep, ...]
    is_default: bool = False
    default_prompt: str = ""


AGENT_LABELS: dict[str, str] = {
    "prd": "PRD",
    "techspec": "Techspec",
    "tasks": "Tasks",
    "implement": "Implementar",
    "review": "Review",
    "review-fix": "Fix review",
    "quick-plan": "Quick plan",
    "quick-implement": "Quick implement",
    "setup-interview": "Setup — entrevista",
    "setup-artifacts": "Setup — artefatos",
    "codebase-explore": "Explorar codebase",
    "codebase-docs": "Docs de codebase",
}

WORKFLOWS: tuple[FactoryWorkflow, ...] = (
    FactoryWorkflow(
        id="new-issue",
        label="Nova spec",
        description="da ideia ao código revisado",
        steps=(
            FactoryStep("prd", "PRD", True),
            FactoryStep("techspec", "Techspec", True),
            FactoryStep("tasks", "Tasks", True),
            FactoryStep("implement", "Implementar", False, fan_out=True),
            FactoryStep("review", "Review", True),
            FactoryStep(
                "review-fix",
                "Fix review",
                False,
                repeat_from="review",
                repeat_max=3,
            ),
        ),
    ),
    FactoryWorkflow(
        id="quick-fix",
        label="Correção rápida",
        description="mudança pequena, até 3 arquivos",
        steps=(
            FactoryStep("quick-plan", "Plano", True),
            FactoryStep("quick-implement", "Implementar", False),
        ),
    ),
    FactoryWorkflow(
        id="review",
        label="Review",
        description="branch atual contra a main",
        steps=(
            FactoryStep("review", "Review", True, phase="STANDALONE"),
            FactoryStep(
                "review-fix",
                "Fix review",
                False,
                repeat_from="review",
                repeat_max=3,
                phase="STANDALONE",
            ),
        ),
        default_prompt="Revisar a branch atual",
    ),
    FactoryWorkflow(
        id="setup-project",
        label="Setup do projeto",
        description="gera os artefatos base",
        steps=(
            FactoryStep("setup-interview", "Entrevista", False),
            FactoryStep("setup-artifacts", "Artefatos", False),
        ),
        default_prompt="Novo projeto",
    ),
    FactoryWorkflow(
        id="analyze-codebase",
        label="Analisar codebase",
        description="documenta o repositório",
        steps=(
            FactoryStep("codebase-explore", "Exploração", False),
            FactoryStep("codebase-docs", "Documentação", False),
        ),
        default_prompt="Mapear codebase existente",
    ),
    FactoryWorkflow(
        id="default",
        label="Executar",
        description="tarefa livre, sem etapas",
        steps=(FactoryStep("default", "Executar", True, step_id="run"),),
        is_default=True,
    ),
)


def factory_dir() -> Path:
    return Path(__file__).resolve().parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _expand_includes(text: str) -> str:
    shared = factory_dir() / "shared"

    def _replace(match: re.Match[str]) -> str:
        return _read(shared / f"{match.group(1)}.md").rstrip("\n")

    return INCLUDE.sub(_replace, text)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Shallow YAML frontmatter of an `AGENT.md` and the body after it."""
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, parts[2].lstrip("\n")


@dataclass(frozen=True)
class FactoryAgent:
    id: str
    label: str
    permission_policy: str
    instructions: str
    prompt_template: str


@lru_cache(maxsize=None)
def load_phase(agent_id: str, phase: str = "PHASE") -> str:
    """A step's `prompt_template`: the `<phase>.md` in the agent's folder.

    Cached because an agent may appear in more than one step.
    """
    return _expand_includes(_read(factory_dir() / "agents" / agent_id / f"{phase}.md")).strip()


@lru_cache(maxsize=1)
def load_agents() -> tuple[FactoryAgent, ...]:
    """Read the factory `.md` files (cached; only seeding needs them).

    Frontmatter `runtime` and `model` are left out of the row: an empty value in
    `agent_defs` means "use the machine default", and a concrete value would
    freeze the `pulse init` choice. Per-agent pinning lives in `agent_settings`.
    """
    agents: list[FactoryAgent] = []
    root = factory_dir() / "agents"
    for agent_id, label in AGENT_LABELS.items():
        directory = root / agent_id
        meta, body = parse_frontmatter(_read(directory / "AGENT.md"))
        agents.append(
            FactoryAgent(
                id=agent_id,
                label=label,
                permission_policy=meta.get("permission_policy", ""),
                instructions=body.strip(),
                prompt_template=load_phase(agent_id),
            )
        )
    return tuple(agents)


def seed(connection: Any) -> None:
    """Write the factory configuration. `INSERT OR IGNORE`: never undoes edits.

    An agent or step deleted from the DB is restored on the next open, since
    intentional deletions are not tracked.
    """
    agents = [
        (agent.id, agent.label, agent.permission_policy, agent.instructions)
        for agent in load_agents()
    ]
    agents.append(("default", "Agente", "", ""))
    connection.executemany(
        """
        INSERT OR IGNORE INTO agent_defs (id, label, runtime, model, permission_policy, instructions)
        VALUES (?, ?, '', '', ?, ?)
        """,
        agents,
    )

    def template(step: FactoryStep) -> str:
        if step.agent_id == "default":
            return "{{user_prompt}}"
        return load_phase(step.agent_id, step.phase or "PHASE")

    connection.executemany(
        """
        INSERT OR IGNORE INTO workflow_defs
          (id, label, description, is_default, default_prompt)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (item.id, item.label, item.description, int(item.is_default), item.default_prompt)
            for item in WORKFLOWS
        ],
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO workflow_steps
          (workflow_id, step_id, position, label, agent_id, prompt_template,
           requires_approval, fan_out, repeat_from, repeat_max)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                workflow.id,
                step.id(),
                position,
                step.label,
                step.agent_id,
                template(step),
                int(step.requires_approval),
                int(step.fan_out),
                step.repeat_from,
                int(step.repeat_max),
            )
            for workflow in WORKFLOWS
            for position, step in enumerate(workflow.steps, start=1)
        ],
    )


def inherit_policy_on_default_agent(connection: Any) -> None:
    """Make DBs seeded with `ask` on the `default` agent inherit the policy.

    A hardcoded `ask` overrode machine and project policy in
    `_resolve_pulse_agent`. Idempotent: after the first open no row matches.
    """
    connection.execute(
        "UPDATE agent_defs SET permission_policy = '' WHERE id = 'default' AND permission_policy = 'ask'"
    )


def backfill_default_prompts(connection: Any) -> None:
    """Fill `default_prompt` in DBs seeded before the column existed.

    The `ALTER` gives existing rows `''` and `seed` does not rerun. Only empty
    values are touched, so user-edited loops are preserved.
    """
    connection.executemany(
        "UPDATE workflow_defs SET default_prompt = ? WHERE id = ? AND default_prompt = ''",
        [(item.default_prompt, item.id) for item in WORKFLOWS if item.default_prompt],
    )


APPROVAL_MARK = "Aprovar {{step_label}} e avançar?"

UNATTENDED_STEPS: tuple[tuple[str, str], ...] = (
    ("setup-project", "setup-interview"),
    ("analyze-codebase", "codebase-explore"),
)


def drop_approval_from_unattended_steps(connection: Any) -> None:
    """Remove the approval request from these steps in already-seeded DBs.

    `seed` never rewrites existing rows, so only rows still carrying the factory
    approval block are updated; user-rewritten templates are left alone. Runs on
    every DB open, so it exits early via `SELECT` before calling `load_agents`.
    """
    placeholders = ",".join("?" * len(UNATTENDED_STEPS))
    pending = connection.execute(
        f"""
        SELECT count(*) FROM workflow_steps
         WHERE step_id IN ({placeholders}) AND instr(prompt_template, ?) > 0
        """,  # noqa: S608
        (*(step_id for _workflow_id, step_id in UNATTENDED_STEPS), APPROVAL_MARK),
    ).fetchone()[0]
    if not pending:
        return

    templates = {agent.id: agent.prompt_template for agent in load_agents()}
    connection.executemany(
        """
        UPDATE workflow_steps
           SET requires_approval = 0, prompt_template = ?
         WHERE workflow_id = ? AND step_id = ? AND instr(prompt_template, ?) > 0
        """,
        [
            (templates[step_id], workflow_id, step_id, APPROVAL_MARK)
            for workflow_id, step_id in UNATTENDED_STEPS
        ],
    )


def _count_present(connection: Any, table: str, column: str, ids: tuple[str, ...]) -> int:
    placeholders = ",".join("?" * len(ids))
    query = f"SELECT count(*) FROM {table} WHERE {column} IN ({placeholders})"  # noqa: S608
    return int(connection.execute(query, ids).fetchone()[0])


def is_seeded(connection: Any) -> bool:
    """Whether every factory row is already present.

    Called on every `connect`, so it only counts factory ids instead of
    rereading the playbooks; user-created rows are ignored.
    """
    agent_ids = (*AGENT_LABELS, "default")
    if _count_present(connection, "agent_defs", "id", agent_ids) != len(agent_ids):
        return False
    workflow_ids = tuple(item.id for item in WORKFLOWS)
    if _count_present(connection, "workflow_defs", "id", workflow_ids) != len(workflow_ids):
        return False
    steps = sum(len(item.steps) for item in WORKFLOWS)
    return _count_present(connection, "workflow_steps", "workflow_id", workflow_ids) == steps
