"""O laço de steps: uma faixa da definição que pode rodar mais de uma vez.

Quem permite o laço é a definição (`repeat_from`, `repeat_max` em
[pulse.store.workflow_defs]); quem pede a volta, ou o fim, é o agente, no campo
`next` do bloco de desfecho ([pulse.orchestrator.outcome]). O motor só pergunta
aqui para onde a run vai depois de um desses pedidos — nenhuma regra daqui
conhece fase por nome.
"""

from __future__ import annotations

from dataclasses import dataclass

from pulse.store import runs as run_store
from pulse.store.runs import DONE, PENDING, SETTLED, SKIPPED
from pulse.store.workflow_defs import WorkflowDef

#: Desfecho interno de `_attempt_step`: o step entregou **e** pediu outra volta
#: do laço. Não é status de banco — em `run_steps` ele é `done` como qualquer
#: outro, porque entregou mesmo. Só o laço do motor precisa saber a diferença.
REPEAT = "repeat"
#: Desfecho interno de `_attempt_step`: quem abre o laço entregou e declarou que
#: não sobrou nada a corrigir. O laço termina nele, e o resto da faixa não roda.
CLOSE = "close"


@dataclass(frozen=True)
class Loop:
    """Uma faixa repetível da definição."""

    start: int
    #: Índice do step que fecha o trecho e pode pedir a volta.
    end: int


def find_loops(definition: WorkflowDef) -> dict[int, Loop]:
    """Faixas repetíveis da definição, por índice de step.

    Lido uma vez por run. Um `repeat_from` que não aponta para um step **antes**
    deste é ignorado em silêncio: um alvo à frente, ou inexistente, seria um laço
    que nunca fecha, e o motor prefere rodar a lista reta a travar a run.

    Faixa que cruza outra já achada também é ignorada: com um índice só por
    step, a segunda sobrescrevia a primeira e a volta pedida por uma caía no
    começo da outra.
    """
    found: dict[int, Loop] = {}
    at = {step.step_id: index for index, step in enumerate(definition.steps)}
    for end, step in enumerate(definition.steps):
        if not step.repeat_from or step.repeat_max < 2:
            continue
        start = at.get(step.repeat_from)
        if start is None or start >= end:
            continue
        span = range(start, end + 1)
        if any(index in found for index in span):
            continue
        loop = Loop(start=start, end=end)
        for index in span:
            found[index] = loop
    return found


def repeat_loop(
    run: run_store.RunRecord, definition: WorkflowDef, loop: Loop, label: str
) -> tuple[int | None, str]:
    """Atende o pedido de outra volta: `(índice para onde a run volta, aviso)`.

    Índice `None` quando o teto já foi atingido — a run segue reta e o aviso diz
    por quê.

    O teto conta as rodadas de quem **abre** a faixa, lidas do banco: um
    contador em memória voltava a 1 ao retomar a run, e o laço ganhava voltas
    que o teto não permitia.
    """
    ceiling = definition.steps[loop.end].repeat_max
    opener = run.step(definition.steps[loop.start].step_id)
    number = opener.rounds if opener is not None else 1
    if number >= ceiling:
        return None, f"{label}: teto de {ceiling} rodadas atingido — o que sobrou vai no relatório"
    last = number + 1 >= ceiling
    reopen_loop(run, definition, loop, last=last)
    if not last:
        return loop.start, f"{label} pediu a {number + 1}ª rodada"
    who = opener.label if opener else "o início do laço"
    return loop.start, f"{label} pediu a {number + 1}ª rodada — a última: só {who} roda"


def reopen_loop(
    run: run_store.RunRecord,
    definition: WorkflowDef,
    loop: Loop,
    *,
    last: bool = False,
) -> None:
    """Devolve os steps da faixa para `pending` e conta mais uma volta.

    A volta reusa os mesmos `step_id`, de propósito: é o que mantém **uma linha
    por step** no painel, com o contador do lado, em vez de uma linha por
    rodada. Também é o que faz o log e os artefatos de todas as voltas ficarem
    sob o mesmo step — selecionar `Review` mostra `round-001.md` e
    `round-002.md` lado a lado.

    O preço é conhecido: `run_steps` guarda o estado da **última** volta, não de
    cada uma. O que de fato distingue uma rodada da outra está no arquivo que
    ela escreveu e nos eventos da run, que são append-only.

    O contador vai no step que **abre** a faixa, não no que a fecha: é ele que
    tem um artefato por volta para a pessoa abrir.

    **A última volta (`last`) reabre só quem abre a faixa.** Quem fecha o laço
    pede a volta porque mexeu em algo que ninguém conferiu ainda — deixá-lo
    rodar de novo no teto daria a ele a última palavra sobre o próprio reparo.
    Os demais steps da faixa continuam `done` da volta anterior, e o laço
    principal os pula como qualquer step já fechado.

    O tempo **soma** entre as voltas: o que a volta anterior gastou vai para
    `carried_seconds` antes de `started_at`/`ended_at` reabrirem. Ver
    [pulse.store.runs.carry_round].
    """
    steps = definition.steps[loop.start : loop.start + 1 if last else loop.end + 1]
    for step in steps:
        record = run.step(step.step_id)
        if record is None:
            continue
        if step.step_id == definition.steps[loop.start].step_id:
            record.rounds += 1
        record.carried_seconds = run_store.carry_round(run.id, step.step_id)
        record.waiting_seconds = 0.0
        record.status = PENDING
        record.summary = ""
        record.started_at = ""
        record.ended_at = ""
        record.acp_session_id = ""
        run_store.save_step(run.id, record)


def close_loop(run: run_store.RunRecord, definition: WorkflowDef, loop: Loop) -> int:
    """Fecha o resto da faixa sem rodar e devolve o índice onde a run segue.

    É o fim do laço que o desenho pede — quem atesta que não sobrou nada é quem
    revisa, não quem conserta. Sem isto, um review limpo ainda pedia aprovação
    e mandava um fix rodar só para confirmar que não havia rodada nova.

    Um step que já rodou numa volta anterior fica `done` — ele entregou, e o
    painel não pode dizer o contrário. Só o que nunca rodou nesta run vira
    `skipped`.
    """
    opener = run.step(definition.steps[loop.start].step_id)
    ran_before = opener is not None and opener.rounds > 1
    for step in definition.steps[loop.start + 1 : loop.end + 1]:
        record = run.step(step.step_id)
        if record is None or record.status in SETTLED:
            continue
        record.status = DONE if ran_before else SKIPPED
        record.summary = ""
        record.ended_at = record.ended_at or run_store.utc_now()
        run_store.save_step(run.id, record)
    return loop.end + 1
