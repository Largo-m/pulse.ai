"""Definições de workflow, step e agente — a única fonte do que o Pulse roda.

O Pulse não tem catálogo em código. Quem responde "quais workflows existem" e
"qual o próximo agente" é esta tabela; o pacote não traz `.md` nem `.py` com
nome de fase. A configuração de fábrica é semeada em [pulse.store.db] na
primeira abertura do banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pulse.store.db import connect, default_db_path


@dataclass(frozen=True)
class AgentDef:
    id: str
    label: str
    #: Vazio = cai no padrão da máquina. Ver `pulse.config.resolved`.
    runtime: str = ""
    model: str = ""
    permission_policy: str = "ask"
    instructions: str = ""


@dataclass(frozen=True)
class StepDef:
    workflow_id: str
    step_id: str
    position: int
    label: str
    agent_id: str
    prompt_template: str
    requires_approval: bool
    #: Roda uma vez por item que o step anterior enumerou. Ver
    #: [pulse.orchestrator.fanout].
    fan_out: bool = False
    #: Exige o bloco `pulse:outcome` para fechar como concluído. Ver
    #: [pulse.orchestrator.outcome]. Sem efeito quando há aprovação: ali quem
    #: atesta a entrega é a pessoa.
    requires_outcome: bool = True
    #: `step_id` de um step anterior. Preenchido, este step pode mandar a run
    #: voltar até lá e repetir o trecho — ver [pulse.orchestrator.engine]. Quem
    #: pede a volta é o agente (`next: repeat`); esta coluna é a permissão.
    repeat_from: str = ""
    #: Teto de voltas, contando a primeira. Zero = não repete.
    repeat_max: int = 0


@dataclass(frozen=True)
class WorkflowDef:
    id: str
    label: str
    description: str = ""
    is_default: bool = False
    #: Tarefa que o loop já sabe qual é (ex.: "Mapear codebase existente"). Com
    #: valor, o menu entra direto na run em vez de pedir texto ao usuário.
    default_prompt: str = ""
    steps: tuple[StepDef, ...] = ()


def _agent(row: Any) -> AgentDef:
    return AgentDef(
        id=str(row["id"]),
        label=str(row["label"]),
        runtime=str(row["runtime"] or ""),
        model=str(row["model"] or ""),
        permission_policy=str(row["permission_policy"] or "ask"),
        instructions=str(row["instructions"] or ""),
    )


def _step(row: Any) -> StepDef:
    return StepDef(
        workflow_id=str(row["workflow_id"]),
        step_id=str(row["step_id"]),
        position=int(row["position"]),
        label=str(row["label"]),
        agent_id=str(row["agent_id"]),
        prompt_template=str(row["prompt_template"] or ""),
        requires_approval=bool(row["requires_approval"]),
        fan_out=bool(row["fan_out"]),
        requires_outcome=bool(row["requires_outcome"]),
        repeat_from=str(row["repeat_from"] or ""),
        repeat_max=int(row["repeat_max"] or 0),
    )


def _workflow(row: Any, steps: tuple[StepDef, ...]) -> WorkflowDef:
    return WorkflowDef(
        id=str(row["id"]),
        label=str(row["label"]),
        description=str(row["description"] or ""),
        is_default=bool(row["is_default"]),
        default_prompt=str(row["default_prompt"] or ""),
        steps=steps,
    )


def list_workflows(*, db_path: Path | None = None) -> list[WorkflowDef]:
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            "SELECT * FROM workflow_defs ORDER BY is_default DESC, label"
        ).fetchall()
        return [_workflow(row, _steps_for(connection, str(row["id"]))) for row in rows]
    finally:
        connection.close()


def get_workflow(workflow_id: str, *, db_path: Path | None = None) -> WorkflowDef | None:
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute(
            "SELECT * FROM workflow_defs WHERE id = ?", (workflow_id,)
        ).fetchone()
        if row is None:
            return None
        return _workflow(row, _steps_for(connection, workflow_id))
    finally:
        connection.close()


def _steps_for(connection: Any, workflow_id: str) -> tuple[StepDef, ...]:
    rows = connection.execute(
        "SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY position, step_id",
        (workflow_id,),
    ).fetchall()
    return tuple(_step(row) for row in rows)


def get_agent(agent_id: str, *, db_path: Path | None = None) -> AgentDef | None:
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute("SELECT * FROM agent_defs WHERE id = ?", (agent_id,)).fetchone()
    finally:
        connection.close()
    return _agent(row) if row is not None else None


def list_agents(*, db_path: Path | None = None) -> list[AgentDef]:
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute("SELECT * FROM agent_defs ORDER BY label").fetchall()
    finally:
        connection.close()
    return [_agent(row) for row in rows]


def save_agent(agent: AgentDef, *, db_path: Path | None = None) -> None:
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO agent_defs (id, label, runtime, model, permission_policy, instructions)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              label = excluded.label,
              runtime = excluded.runtime,
              model = excluded.model,
              permission_policy = excluded.permission_policy,
              instructions = excluded.instructions
            """,
            (
                agent.id,
                agent.label,
                agent.runtime,
                agent.model,
                agent.permission_policy,
                agent.instructions,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def save_workflow(workflow: WorkflowDef, *, db_path: Path | None = None) -> None:
    """Grava a definição e substitui os steps.

    Os steps são reescritos por inteiro, não mesclados: um step removido da
    definição tem de sumir, e casar por id deixaria órfão silencioso.
    """
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO workflow_defs (id, label, description, is_default)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              label = excluded.label,
              description = excluded.description,
              is_default = excluded.is_default
            """,
            (workflow.id, workflow.label, workflow.description, int(workflow.is_default)),
        )
        connection.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (workflow.id,))
        connection.executemany(
            """
            INSERT INTO workflow_steps
              (workflow_id, step_id, position, label, agent_id, prompt_template,
               requires_approval, fan_out, requires_outcome, repeat_from, repeat_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    workflow.id,
                    step.step_id,
                    index,
                    step.label,
                    step.agent_id,
                    step.prompt_template,
                    int(step.requires_approval),
                    int(step.fan_out),
                    int(step.requires_outcome),
                    step.repeat_from,
                    int(step.repeat_max),
                )
                for index, step in enumerate(workflow.steps, start=1)
            ],
        )
        connection.commit()
    finally:
        connection.close()


def delete_workflow(workflow_id: str, *, db_path: Path | None = None) -> None:
    connection = connect(db_path or default_db_path())
    try:
        connection.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (workflow_id,))
        connection.execute("DELETE FROM workflow_defs WHERE id = ?", (workflow_id,))
        connection.commit()
    finally:
        connection.close()
