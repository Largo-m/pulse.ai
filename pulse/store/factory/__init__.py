"""Configuração de fábrica: as linhas que o Pulse já nasce sabendo rodar.

Isto **não** é um catálogo em código. Nada aqui é lido durante uma run: o motor
([pulse.orchestrator.engine]) só conhece `workflow_defs`, `workflow_steps` e
`agent_defs`. Este pacote roda uma vez, na primeira abertura do banco, converte
os `.md` de fábrica em linha e sai do caminho. Depois disso o banco manda —
editar um loop é `UPDATE`, não release.

Os `.md` ficam em arquivo em vez de string Python porque são ~8 mil linhas de
playbook que alguém precisa revisar em diff. O que o banco guarda é o texto já
resolvido: os `<!-- include: nome -->` de `shared/` são expandidos aqui, na
semeadura, para a linha do banco ser autossuficiente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

#: `<!-- include: nome -->` → `shared/nome.md`. Marcador de comentário, e não
#: `{{nome}}`, para não colidir com os placeholders que o motor resolve por run.
INCLUDE = re.compile(r"^[ \t]*<!--[ \t]*include:[ \t]*([a-z0-9-]+)[ \t]*-->[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class FactoryStep:
    agent_id: str
    label: str
    requires_approval: bool
    #: Roda uma vez por item que o step anterior enumerou, cada um em sessão
    #: isolada e com linha própria no painel. Ver [pulse.orchestrator.fanout].
    fan_out: bool = False
    #: Default = o id do agente, que é único dentro de cada loop de fábrica.
    #: Explícito só onde já existe linha gravada com outro id — trocar o id
    #: criaria um segundo step em vez de atualizar o primeiro.
    step_id: str = ""

    def id(self) -> str:
        return self.step_id or self.agent_id


@dataclass(frozen=True)
class FactoryWorkflow:
    id: str
    label: str
    description: str
    steps: tuple[FactoryStep, ...]
    is_default: bool = False
    #: Loop que já sabe qual é a tarefa — o menu entra direto na run, sem pedir
    #: texto. Vazio = o usuário descreve o que quer.
    default_prompt: str = ""


#: Rótulo de cada agente na UI. O resto (runtime, model, policy, descrição) sai
#: do frontmatter do próprio `AGENT.md` — um lugar só para editar.
AGENT_LABELS: dict[str, str] = {
    "prd": "PRD",
    "techspec": "Techspec",
    "tasks": "Tasks",
    "implement": "Implementar",
    "quick-plan": "Quick plan",
    "quick-implement": "Quick implement",
    "setup-interview": "Setup — entrevista",
    "setup-artifacts": "Setup — artefatos",
    "codebase-explore": "Explorar codebase",
    "codebase-docs": "Docs de codebase",
}

#: Os loops. Um step é `(agente, rótulo, pede aprovação)` — e a ordem é a lista.
#: Não há ramificação: o motor percorre a lista. Quem escolhe entre spec completa
#: e correção rápida é o usuário, no menu; e o `quick-plan` refaz a checagem de
#: escopo, então um pedido grande que entrou pelo loop errado para no primeiro
#: step em vez de seguir.
WORKFLOWS: tuple[FactoryWorkflow, ...] = (
    FactoryWorkflow(
        id="new-issue",
        label="Nova spec",
        description="pipeline completo",
        steps=(
            FactoryStep("prd", "PRD", True),
            FactoryStep("techspec", "Techspec", True),
            FactoryStep("tasks", "Tasks", True),
            FactoryStep("implement", "Implementar", False, fan_out=True),
        ),
    ),
    FactoryWorkflow(
        id="quick-fix",
        label="Correção rápida",
        description="até 3 arquivos",
        steps=(
            FactoryStep("quick-plan", "Plano", True),
            FactoryStep("quick-implement", "Implementar", False),
        ),
    ),
    FactoryWorkflow(
        id="setup-project",
        label="Setup do projeto",
        description="artefatos do projeto",
        steps=(
            FactoryStep("setup-interview", "Entrevista", False),
            FactoryStep("setup-artifacts", "Artefatos", False),
        ),
        default_prompt="Novo projeto",
    ),
    FactoryWorkflow(
        id="analyze-codebase",
        label="Analisar codebase",
        description="docs do repositório",
        steps=(
            FactoryStep("codebase-explore", "Exploração", False),
            FactoryStep("codebase-docs", "Documentação", False),
        ),
        default_prompt="Mapear codebase existente",
    ),
    FactoryWorkflow(
        id="default",
        label="Executar",
        description="sem pipeline",
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
    """Frontmatter YAML raso do `AGENT.md` e o corpo depois dele."""
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


@lru_cache(maxsize=1)
def load_agents() -> tuple[FactoryAgent, ...]:
    """Lê os `.md` de fábrica. Em cache: só a semeadura precisa disso.

    `runtime` e `model` do frontmatter são preferência de quem escreveu o
    playbook, não o que a máquina tem — ficam de fora da linha. Campo vazio em
    `agent_defs` significa "use o padrão da máquina", e gravar um valor concreto
    congelaria a escolha feita no `pulse init`. Quem quiser fixar o par por
    agente faz isso na tela de configurações, que grava em `agent_settings`.
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
                permission_policy=meta.get("permission_policy", "ask"),
                instructions=body.strip(),
                prompt_template=_expand_includes(_read(directory / "PHASE.md")).strip(),
            )
        )
    return tuple(agents)


def seed(connection: Any) -> None:
    """Grava a configuração de fábrica. `INSERT OR IGNORE`: nunca desfaz edição.

    Um agente ou step apagado do banco volta ao padrão na abertura seguinte — é
    a mesma promessa que o `SEED` de [pulse.store.db] já fazia, e é o que dá para
    prometer sem guardar "o usuário apagou isto de propósito".
    """
    agents = [
        (agent.id, agent.label, agent.permission_policy, agent.instructions)
        for agent in load_agents()
    ]
    # O agente genérico do workflow `default` não tem playbook nem fase: ele é o
    # escape — o que o usuário pedir vai cru para o runtime configurado.
    agents.append(("default", "Agente", "ask", ""))
    connection.executemany(
        """
        INSERT OR IGNORE INTO agent_defs (id, label, runtime, model, permission_policy, instructions)
        VALUES (?, ?, '', '', ?, ?)
        """,
        agents,
    )

    templates = {agent.id: agent.prompt_template for agent in load_agents()}
    templates["default"] = "{{user_prompt}}"
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
           requires_approval, fan_out)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                workflow.id,
                step.id(),
                position,
                step.label,
                step.agent_id,
                templates[step.agent_id],
                int(step.requires_approval),
                int(step.fan_out),
            )
            for workflow in WORKFLOWS
            for position, step in enumerate(workflow.steps, start=1)
        ],
    )


def backfill_default_prompts(connection: Any) -> None:
    """Preenche `default_prompt` nos bancos semeados antes da coluna existir.

    O `ALTER` dá `''` a toda linha que já estava lá, e `seed` não roda num banco
    já semeado — sem isto, "Analisar codebase" e "Setup do projeto" voltariam a
    pedir texto em quem já usa o Pulse. Só toca no que está vazio: o loop que o
    usuário editou continua como ele deixou.
    """
    connection.executemany(
        "UPDATE workflow_defs SET default_prompt = ? WHERE id = ? AND default_prompt = ''",
        [(item.default_prompt, item.id) for item in WORKFLOWS if item.default_prompt],
    )


#: Trecho que só existe num `prompt_template` que ainda manda o agente pedir
#: aprovação. É o sinal de "esta linha é a de fábrica antiga", e some no próprio
#: UPDATE — por isso `drop_approval_from_unattended_steps` é idempotente.
APPROVAL_MARK = "Aprovar {{step_label}} e avançar?"

#: Steps que pediam aprovação e não pedem mais: os dois loops que rodam do
#: começo ao fim sem ninguém olhando. `(workflow_id, step_id)`.
UNATTENDED_STEPS: tuple[tuple[str, str], ...] = (
    ("setup-project", "setup-interview"),
    ("analyze-codebase", "codebase-explore"),
)


def drop_approval_from_unattended_steps(connection: Any) -> None:
    """Tira o pedido de aprovação desses steps nos bancos já semeados.

    `seed` é `INSERT OR IGNORE` e não reescreve linha existente, então mudar o
    playbook de fábrica não chega a quem já usa o Pulse. Aqui chega — mas só na
    linha que ainda carrega o bloco de aprovação de fábrica: template que o
    usuário reescreveu não é tocado.

    Roda em toda abertura do banco, então sai cedo pelo `SELECT`: depois do
    primeiro UPDATE nenhuma linha casa, e `load_agents` — que relê ~8 mil linhas
    de playbook — nem chega a ser chamado.
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
    """Toda linha de fábrica já está lá?

    O `connect` é por operação, e reler ~8 mil linhas de playbook em cada um
    seria caro à toa. Conta só os ids de fábrica: linha que o usuário criou não
    entra na conta, e linha de fábrica que sumiu derruba o teste e volta.
    """
    agent_ids = (*AGENT_LABELS, "default")
    if _count_present(connection, "agent_defs", "id", agent_ids) != len(agent_ids):
        return False
    workflow_ids = tuple(item.id for item in WORKFLOWS)
    if _count_present(connection, "workflow_defs", "id", workflow_ids) != len(workflow_ids):
        return False
    steps = sum(len(item.steps) for item in WORKFLOWS)
    return _count_present(connection, "workflow_steps", "workflow_id", workflow_ids) == steps
