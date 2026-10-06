"""O segundo protocolo que o Pulse lê da resposta do agente: a lista de itens.

O primeiro é o questionário de aprovação ([pulse.prompts.approval]). Este existe
porque um step às vezes não é *um* trabalho: "implementar as tasks" são N
trabalhos, e cada um merece sessão isolada e linha própria no painel — mas
quantos são só se sabe depois que o step anterior rodou.

O motor continua sem ler artefato. Ele não abre `tasks.md`, não conhece `### T1`
nem nome de arquivo nenhum: quem enumera é o agente, num bloco cercado que o
Pulse sabe achar. Trocar `tasks.md` por outra coisa não muda uma linha daqui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.store.workflow_defs import StepDef

#: ```pulse:items … ``` — cercado e nomeado para não colidir com um bloco de
#: código que o agente tenha citado no mesmo texto.
BLOCK = re.compile(r"```pulse:items[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
#: `T1 — Criar o endpoint` / `T1 - Criar o endpoint` / `T1: Criar o endpoint`.
#: O id é o que o prompt do item vai citar; o título é o que aparece no painel.
ITEM = re.compile(r"^[ \t>*-]*([^\s:—–-][^:—–]*?)[ \t]*[:—–-][ \t]*(\S.*)$")

#: Teto de segurança. Um agente que devolve 200 itens errou a conta, e abrir 200
#: sessões ACP sairia caro antes de alguém perceber.
MAX_ITEMS = 40
#: Espaço entre as posições da definição, para o fan-out caber no meio sem
#: renumerar o resto: o step 4 vira 4001, 4002… e continua antes do step 5.
POSITION_STRIDE = 1000


@dataclass(frozen=True)
class Item:
    id: str
    label: str


def parse_items(text: str) -> tuple[Item, ...]:
    """Itens do último bloco `pulse:items`. Texto sem bloco devolve vazio.

    O último, e não o primeiro: quando o agente reapresenta a lista depois de um
    ajuste, a versão que vale é a de baixo.
    """
    matches = BLOCK.findall(text or "")
    if not matches:
        return ()
    items: list[Item] = []
    seen: set[str] = set()
    for line in matches[-1].splitlines():
        match = ITEM.match(line.strip())
        if match is None:
            continue
        item_id = match.group(1).strip()
        # Id repetido viraria `step_id` duplicado, e `run_steps` tem chave
        # (run_id, step_id): o segundo sobrescreveria o primeiro em silêncio.
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        items.append(Item(id=item_id, label=match.group(2).strip()))
        if len(items) >= MAX_ITEMS:
            break
    return tuple(items)


def expand(
    run: run_store.RunRecord, step: StepDef, previous_summary: str
) -> list[tuple[StepDef, Item | None]]:
    """O step da definição vira os steps que a run vai mesmo rodar.

    Sem `fan_out`, é ele mesmo. Com, é um por item que o step anterior
    enumerou — cada um com `step_id` próprio, porque cada um quer sessão
    isolada, linha no painel e a chance de ser refeito sozinho.

    Lista vazia (o agente não emitiu o bloco, ou emitiu vazio) roda o step uma
    vez, como se `fan_out` não existisse: um protocolo que o agente não seguiu
    não é motivo para a run parar.
    """
    if not step.fan_out:
        return [(step, None)]

    items = parse_items(previous_summary)
    if not items:
        return [(step, None)]

    base = run.step(step.step_id)
    base_position = base.position if base is not None else step.position * POSITION_STRIDE
    at = len(run.steps)
    if base is not None:
        # O placeholder cumpriu o papel de mostrar que o step existe; agora os
        # N filhos tomam o lugar dele — no mesmo ponto da lista, senão o painel
        # mostraria as tasks depois de um step que ainda nem rodou.
        at = run.steps.index(base)
        run.steps.remove(base)
        run_store.delete_step(run.id, step.step_id)

    units: list[tuple[StepDef, Item | None]] = []
    for index, item in enumerate(items, start=1):
        step_id = f"{step.step_id}:{item.id}"
        label = item.label or item.id
        position = base_position + index
        units.append(
            (
                StepDef(
                    workflow_id=step.workflow_id,
                    step_id=step_id,
                    position=position,
                    label=label,
                    agent_id=step.agent_id,
                    prompt_template=step.prompt_template,
                    requires_approval=step.requires_approval,
                ),
                item,
            )
        )
        if run.step(step_id) is None:
            child = StepRecord(
                step_id=step_id,
                position=position,
                label=label,
                agent_id=step.agent_id,
            )
            run.steps.insert(at + index - 1, child)
            # Grava os N na hora, não quando cada um começar. Filho que só
            # existe na memória some se a run cair no meio do fan-out: o
            # histórico reabria com as tasks que já tinham rodado e mais
            # nenhuma, como se o agente tivesse enumerado menos do que enumerou.
            run_store.save_step(run.id, child)
    return units
