"""O orquestrador: qual agente roda agora e quando.

Esta é a única máquina de estados do Pulse, e ela não sabe nada sobre o que os
agentes fazem. Um workflow é uma lista ordenada de steps vinda do banco
([pulse.store.workflow_defs]); para cada step o motor resolve o agente, renderiza
o `prompt_template`, abre uma sessão ACP isolada e grava o desfecho em
`run_steps`. Não há fase com nome conhecido, artefato esperado nem ordem fixa.

Isolar a sessão por step é de propósito: o agente do step seguinte não herda o
contexto do anterior, só o resumo que o Pulse repassa. É o que permite trocar de
runtime entre steps e retomar uma run refazendo um step só.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from pulse import vcs
from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.config.paths import worktrees_dir
from pulse.doctor.checks import check_runtime_ready
from pulse.orchestrator.cli_output import (
    print_workflow_banner,
    print_workflow_error,
    print_workflow_result,
)
from pulse.orchestrator.fanout import Item, parse_items
from pulse.orchestrator.outcome import MISSING, Outcome, parse_outcome
from pulse.orchestrator.prompts import (
    build_continuation_prompt,
    build_outcome_reminder_prompt,
    build_unblock_prompt,
    guidance_block,
    outcome_protocol,
)
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.prompts.approval import CANCEL, SKIP, format_summary
from pulse.prompts.permission import PermissionPolicy
from pulse.prompts.render import TemplateError, render
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.runtime.tty import is_cockpit_stream, is_interactive
from pulse.runtimes import get_runtime
from pulse.store import runs as run_store
from pulse.store.runs import (
    BLOCKED,
    DONE,
    FAILED,
    PENDING,
    RUNNING,
    SETTLED,
    SKIPPED,
    StepRecord,
)
from pulse.store.workflow_defs import StepDef, WorkflowDef, get_agent, get_workflow

_SUCCESS_STOPS = frozenset({"end_turn", "end", "stop"})
_POLICIES: dict[str, PermissionPolicy] = {
    "ask": "ask",
    "auto_approve": "auto_approve",
    "deny_writes": "deny_writes",
}
#: Fallback para runner sem controle (CLI, testes): nunca para.
_NEVER_INTERRUPTED = RunControl()
#: Espaço entre as posições da definição, para o fan-out caber no meio sem
#: renumerar o resto: o step 4 vira 4001, 4002… e continua antes do step 5.
POSITION_STRIDE = 1000
#: Código de saída de uma run que parou num step bloqueado. Não é falha nem
#: parada do usuário: nada quebrou e ninguém apertou nada — um step declarou que
#: não tinha como entregar, e a run não passa por cima disso. Vizinho de
#: `RUN_STOPPED`, e como ele: quem vê oferece retomar, não erro.
RUN_BLOCKED = 131
#: Desfecho interno de `_attempt_step`: o step entregou **e** pediu outra volta
#: do laço. Não é status de banco — em `run_steps` ele é `done` como qualquer
#: outro, porque entregou mesmo. Só o laço do motor precisa saber a diferença.
REPEAT = "repeat"


class UnknownWorkflow(ValueError):
    """Id que não existe em `workflow_defs`."""


def run_workflow(
    *,
    workflow_id: str,
    user_prompt: str,
    workspace: Path | None = None,
    stream: Any | None = None,
    prompt_handler: Any | None = None,
    render_header: bool = True,
    resume_run_id: str | None = None,
    control: RunControl | None = None,
    run_id: str | None = None,
) -> int:
    cockpit = is_cockpit_stream(stream)
    if not cockpit and not is_interactive():
        print("[pulse] Workflow requer terminal interativo ou cliente Engine.", file=sys.stderr)
        return 1

    definition = get_workflow(workflow_id)
    if definition is None:
        raise UnknownWorkflow(f"workflow desconhecido: {workflow_id}")
    if not definition.steps:
        message = f"workflow `{workflow_id}` não tem step nenhum"
        if cockpit:
            raise UnknownWorkflow(message)
        print(f"[pulse] {message}", file=sys.stderr)
        return 1

    resolved = resolve_config(workspace=workspace, workflow=workflow_id)
    runtime = get_runtime(resolved.agent_name)
    blocking = check_runtime_ready(runtime.id)
    if blocking is not None:
        message = (
            f"Runtime `{runtime.id}` indisponível: {blocking.message}. "
            f"{blocking.detail or ''}".strip()
        )
        if cockpit:
            raise RuntimeError(message)
        print(f"[pulse] {message}", file=sys.stderr)
        return 1

    workspace_root = resolved.workspace_dir
    run = _resolve_run(
        definition,
        workspace_root,
        user_prompt,
        resume_run_id=resume_run_id,
        run_id=run_id,
    )

    try:
        exec_dir, branch = _prepare_workspace(run, workspace_root, resolved)
    except vcs.GitError as error:
        # Sem o worktree a run só poderia rodar na árvore de trabalho da pessoa
        # — que é exatamente o que a chave pediu para não acontecer. Melhor não
        # começar do que começar no lugar errado.
        message = f"Não consegui abrir o worktree desta run: {error}"
        if cockpit:
            raise RuntimeError(message) from error
        print(f"[pulse] {message}", file=sys.stderr)
        return 1

    _announce_context(stream, exec_dir, branch)

    if render_header and not cockpit:
        lines = [
            f"Workspace: {exec_dir}",
            f"Run: {run.id}",
            f"Steps: {len(run.steps)}",
            f"Tarefa: {run.user_prompt.strip() or '—'}",
        ]
        if branch:
            lines.insert(1, f"Branch: {branch}")
        print_workflow_banner(title=definition.label, lines=lines)

    runner = AcpSessionRunner(
        resolved.acp_command,
        cwd=str(exec_dir),
        permission_policy=resolved.permission_policy,
        stream=stream or NullStreamSink(),
        prompt_handler=prompt_handler or NullPromptPort(),
        runtime=runtime,
        control=control,
    )
    runner.bind_run(run.id)

    try:
        return _execute(
            runner=runner,
            cockpit=cockpit,
            definition=definition,
            run=run,
            workspace=workspace_root,
            exec_dir=exec_dir,
            fallback_model=resolved.model,
        )
    except Exception as error:  # noqa: BLE001
        # Rede de segurança: o que passa por aqui já escapou do menu de retry,
        # então o mínimo é não deixar o step gravado como "executando" — é esse
        # estado que fazia a run voltar do histórico sem retomar nem refazer.
        _fail_running_steps(run)
        run_store.update_run(run.id, status=FAILED)
        if cockpit:
            raise
        print_workflow_error(f"Falha na sessão ACP: {error}")
        return 1


def _resolve_run(
    definition: WorkflowDef,
    workspace: Path,
    user_prompt: str,
    *,
    resume_run_id: str | None,
    run_id: str | None = None,
) -> run_store.RunRecord:
    """A run no banco. `run_id` deixa quem chama batizá-la.

    O daemon passa o id dele: sem isso a run tinha dois nomes — um na API, outro
    no SQLite — e "reabrir a run X" virava chute pela mais recente do workspace.
    """
    if resume_run_id:
        existing = run_store.load_run(resume_run_id)
        if existing is not None:
            return existing
    return run_store.create_run(
        run_id=run_id or str(uuid.uuid4()),
        workflow_id=definition.id,
        workspace=workspace,
        user_prompt=user_prompt,
        steps=[
            StepRecord(
                step_id=step.step_id,
                position=step.position * POSITION_STRIDE,
                label=step.label,
                agent_id=step.agent_id,
            )
            for step in definition.steps
        ],
    )


def _prepare_workspace(
    run: run_store.RunRecord,
    workspace_root: Path,
    resolved: Any,
) -> tuple[Path, str]:
    """Onde esta run trabalha, e em que branch.

    Três casos, nesta ordem:

    1. **Run retomada que já tem worktree.** Reusa o que está gravado. Abrir um
       segundo worktree ao retomar jogaria fora o que o primeiro produziu — o
       trabalho dos steps que já fecharam está lá dentro.
    2. **Sem isolamento** (chave desligada, ou projeto fora de repositório git).
       A run roda na raiz, como sempre rodou, e a branch é a que o projeto tem
       agora. É este caso que faz a branch aparecer na tela de quem nem liga a
       chave.
    3. **Isolamento ligado.** `git worktree add` em `~/.pulse/worktrees/<run>`,
       numa branch nova a partir do HEAD.

    A raiz do projeto continua sendo a identidade da run (`workspace_root`): é
    por ela que o histórico a encontra. O que muda é só onde o agente escreve.
    """
    if run.worktree_path and Path(run.worktree_path).exists():
        return Path(run.worktree_path), run.branch

    repo = vcs.repo_root(workspace_root) if getattr(resolved, "use_worktree", False) else None
    if repo is None:
        branch = vcs.current_branch(workspace_root)
        if branch != run.branch:
            run_store.set_workspace_context(run.id, branch=branch)
        run.branch = branch
        run.worktree_path = ""
        return workspace_root, branch

    target = worktrees_dir() / run.id
    branch = vcs.add_worktree(repo, target, _branch_name(run))
    run_store.set_workspace_context(run.id, worktree_path=str(target), branch=branch)
    run.worktree_path = str(target)
    run.branch = branch
    return target, branch


def _branch_name(run: run_store.RunRecord) -> str:
    """`pulse/<workflow>-<run curto>`.

    O prefixo `pulse/` agrupa na listagem do git e diz de onde a branch veio; o
    pedaço do id da run é o que a liga de volta ao histórico. Nome do workflow e
    não da tarefa: o que o usuário pediu é texto livre, e virar nome de ref
    exigiria higienizar frase inteira.
    """
    slug = "".join(char if char.isalnum() or char in "-_" else "-" for char in run.workflow_id)
    slug = slug.strip("-") or "run"
    return f"pulse/{slug}-{run.id[:8]}"


def _announce_context(stream: Any | None, exec_dir: Path, branch: str) -> None:
    """Diz à tela onde a run trabalha, antes de qualquer step começar.

    Antes do primeiro `phase.begin` de propósito: é por este caminho que o
    painel de artefatos descobre a pasta onde procurar os arquivos, e um
    artefato gravado antes disso seria procurado na raiz errada.
    """
    set_context = getattr(stream, "set_context", None) if stream is not None else None
    if callable(set_context):
        set_context(cwd=str(exec_dir), branch=branch)


def _execute(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    definition: WorkflowDef,
    run: run_store.RunRecord,
    workspace: Path,
    exec_dir: Path,
    fallback_model: str | None,
) -> int:
    runner.start()
    try:
        runner.initialize()
        runner.authenticate()
        _sync_steps(runner, run)

        # Índice, e não `for`: um step pode mandar a run voltar para um anterior
        # e repetir o trecho (`repeat_from`). O laço continua sem ramificação —
        # não há condição sobre id de workflow nem sobre nome de fase: o motor lê
        # um pedido declarado no bloco de desfecho e um teto gravado na
        # definição, e os dois vêm do banco.
        loops = _loops(definition)
        #: Quantas voltas cada laço já deu, por `step_id` de quem fecha o trecho.
        rounds: dict[str, int] = {}
        index = 0
        while index < len(definition.steps):
            definition_step = definition.steps[index]
            at = index
            index += 1
            # Um step de fan-out só sabe quantos trabalhos tem depois que o
            # anterior rodou — por isso a expansão acontece aqui, e não ao criar
            # a run.
            units = _units(run, definition_step)
            _sync_steps(runner, run)

            for step, item in units:
                record = run.step(step.step_id)
                if record is None:
                    # Step acrescentado à definição depois que a run começou:
                    # entra como pendente em vez de ser ignorado silenciosamente.
                    record = StepRecord(
                        step_id=step.step_id,
                        position=step.position,
                        label=step.label,
                        agent_id=step.agent_id,
                    )
                    run.steps.append(record)

                if record.status in SETTLED:
                    continue

                # Parada pedida entre dois steps: encerra aqui, sem nada em voo.
                if not _control(runner).checkpoint():
                    _notify(runner, "Run parada pelo usuário")
                    run_store.update_run(run.id, status="stopped")
                    return RUN_STOPPED

                run_store.update_run(run.id, status=RUNNING, current_step=step.step_id)
                exit_code, repeats = _run_step(
                    runner=runner,
                    cockpit=cockpit,
                    run=run,
                    step=step,
                    record=record,
                    workspace=workspace,
                    exec_dir=exec_dir,
                    fallback_model=fallback_model,
                    item=item,
                )
                _sync_steps(runner, run)
                if exit_code != 0:
                    run_store.update_run(run.id, status=_run_status(exit_code))
                    return exit_code

                if repeats and at in loops:
                    loop = loops[at]
                    number = rounds.get(loop.closer, 1)
                    if number >= definition_step.repeat_max:
                        _notify(
                            runner,
                            f"{record.label}: teto de {definition_step.repeat_max} "
                            "rodadas atingido — o que sobrou vai no relatório",
                        )
                    else:
                        rounds[loop.closer] = number + 1
                        _reopen_loop(run, definition, loop)
                        index = loop.start
                        _sync_steps(runner, run)
                        _notify(runner, f"{record.label} pediu a {number + 1}ª rodada")
                        break

        run_store.update_run(run.id, status="completed")
        if not cockpit:
            print_workflow_result(f"✓ {definition.label} concluído")
        return 0
    finally:
        runner.close()


@dataclass(frozen=True)
class _Loop:
    """Uma faixa repetível da definição."""

    start: int
    #: Índice do step que fecha o trecho e pode pedir a volta.
    end: int
    closer: str


def _loops(definition: WorkflowDef) -> dict[int, _Loop]:
    """Faixas repetíveis da definição, por índice de step.

    Lido uma vez por run. Um `repeat_from` que não aponta para um step **antes**
    deste é ignorado em silêncio: um alvo à frente, ou inexistente, seria um laço
    que nunca fecha, e o motor prefere rodar a lista reta a travar a run.
    """
    found: dict[int, _Loop] = {}
    at = {step.step_id: index for index, step in enumerate(definition.steps)}
    for end, step in enumerate(definition.steps):
        if not step.repeat_from or step.repeat_max < 2:
            continue
        start = at.get(step.repeat_from)
        if start is None or start >= end:
            continue
        loop = _Loop(start=start, end=end, closer=step.step_id)
        for index in range(start, end + 1):
            found[index] = loop
    return found


def _reopen_loop(run: run_store.RunRecord, definition: WorkflowDef, loop: _Loop) -> None:
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
    """
    for step in definition.steps[loop.start : loop.end + 1]:
        record = run.step(step.step_id)
        if record is None:
            continue
        if step.step_id == definition.steps[loop.start].step_id:
            record.rounds += 1
        record.status = PENDING
        record.summary = ""
        record.started_at = ""
        record.ended_at = ""
        record.acp_session_id = ""
        run_store.save_step(run.id, record)


def _run_status(exit_code: int) -> str:
    """Como a run fica registrada quando um step a interrompe.

    Bloqueio não é falha: o histórico precisa distinguir "quebrou" de "ficou
    esperando alguém" para poder oferecer a ação certa quando a run for reaberta.
    """
    if exit_code == RUN_STOPPED:
        return "stopped"
    if exit_code == RUN_BLOCKED:
        return BLOCKED
    return FAILED


def _units(
    run: run_store.RunRecord, step: StepDef
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

    items = parse_items(_previous_summary(run, step.step_id))
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


def _previous_settled(run: run_store.RunRecord, step_id: str) -> StepRecord | None:
    """O último step **que fechou** antes deste e deixou resumo.

    Só `done` e `skipped` contam. Um step que falhou ou travou também deixa
    texto gravado, e passar esse texto adiante era o que fazia o step seguinte
    trabalhar em cima de uma entrega que não existiu — recebendo "não consegui
    migrar o schema" no lugar onde ele espera o que o anterior produziu.

    A parada também acontece no primeiro filho de fan-out (`run:T1` para
    `run`): ao retomar, o step pai já não existe na run, e sem isto a varredura
    ia até o fim e devolvia o resumo da última task — o bloco `pulse:items`
    sumia, o fan-out desmontava e a run voltava a rodar o step pai inteiro.

    O registro inteiro, e não só o texto, porque o step seguinte precisa saber
    **como** o anterior fechou: um step pulado e um concluído entregam o mesmo
    tipo de resumo, e sem o status o pulo só valeria para quem o deu.
    """
    child = f"{step_id}:"
    previous: StepRecord | None = None
    for record in run.steps:
        if record.step_id == step_id or record.step_id.startswith(child):
            break
        if record.summary and record.status in SETTLED:
            previous = record
    return previous


def _previous_summary(run: run_store.RunRecord, step_id: str) -> str:
    record = _previous_settled(run, step_id)
    return record.summary if record is not None else ""


def _run_step(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    run: run_store.RunRecord,
    step: StepDef,
    record: StepRecord,
    workspace: Path,
    exec_dir: Path,
    fallback_model: str | None,
    item: Item | None = None,
) -> tuple[int, bool]:
    """`(código de saída, o agente pediu outra volta do laço)`."""
    guidance = ""
    while True:
        outcome, reason = _attempt_step(
            runner=runner,
            cockpit=cockpit,
            run=run,
            step=step,
            record=record,
            workspace=workspace,
            exec_dir=exec_dir,
            fallback_model=fallback_model,
            guidance=guidance,
            item=item,
        )
        if outcome in {DONE, SKIPPED, REPEAT}:
            return 0, outcome == REPEAT

        # O step não terminou porque o usuário parou a run, não porque falhou:
        # não faz sentido perguntar "quer tentar de novo?" — é só encerrar
        # deixando o step pendente para quem retomar.
        if _control(runner).interrupted:
            _release_step(runner, run=run, record=record, label=record.label)
            return RUN_STOPPED, False

        if outcome == BLOCKED:
            choice, guidance = _offer_blocked(
                runner, f"{record.label} está bloqueado", reason
            )
            if choice == "skip":
                # Pulo explícito, e não o `done` de antes: o step não entregou,
                # e quem vier depois — no painel, no histórico ou no resumo do
                # step seguinte — precisa conseguir ver isso.
                record.status = SKIPPED
                record.ended_at = run_store.utc_now()
                # `summary` é o que este step entrega ao próximo, e um step
                # bloqueado não entregou nada: passar adiante o texto do
                # bloqueio faria o step seguinte trabalhar em cima dele. O que
                # o agente escreveu continua no log da run (`run_events`).
                record.summary = ""
                run_store.save_step(run.id, record)
                _sync_steps(runner, run)
                _notify(runner, f"{record.label} pulado pelo usuário")
                return 0, False
            if choice != "retry":
                _notify(runner, f"Run bloqueada em {record.label}: {reason}")
                return RUN_BLOCKED, False
        else:
            choice, guidance = _offer_retry(runner, f"Step {record.label} falhou", reason)
            if choice != "retry":
                return 1, False
        _revive_session(runner)
        if guidance:
            _notify(runner, f"Refazendo {record.label} com orientação do usuário")
        else:
            _notify(runner, f"Refazendo {record.label}")


def _attempt_step(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    run: run_store.RunRecord,
    step: StepDef,
    record: StepRecord,
    workspace: Path,
    exec_dir: Path,
    fallback_model: str | None,
    guidance: str,
    item: Item | None = None,
) -> tuple[str, str]:
    record.status = RUNNING
    record.started_at = record.started_at or run_store.utc_now()
    run_store.save_step(run.id, record)

    # `workspace` e não `exec_dir`: a config do projeto é achada pelo root
    # registrado em `projects`, e um worktree não está lá. Resolver por ele
    # faria as settings por agente sumirem sem erro nenhum.
    model, instructions = _activate_agent(runner, workspace, step, fallback_model)
    try:
        prompt_text = render(step.prompt_template, _context(run, step, exec_dir, item))
    except TemplateError as error:
        _fail(run, record)
        return FAILED, str(error)
    if instructions:
        prompt_text = f"{instructions}\n\n---\n\n{prompt_text}"
    prompt_text += guidance_block(guidance)

    # Um step tem um portão só. Onde há aprovação, quem atesta a entrega é a
    # pessoa que aprovou; onde não há, é o desfecho que o agente declara. Pedir
    # os dois no mesmo turno seria perguntar duas vezes a mesma coisa.
    declares_outcome = step.requires_outcome and not step.requires_approval
    if declares_outcome:
        prompt_text += outcome_protocol()

    try:
        if step.requires_approval:
            result = runner.run_isolated_phase(
                workflow=run.workflow_id,
                phase_label=record.label or step.step_id,
                initial_prompt=prompt_text,
                preferred_model=model,
                build_continuation=lambda *, phase_summary, questionnaire_answers, outcome, **_: (
                    build_continuation_prompt(
                        step_id=step.step_id,
                        summary=phase_summary,
                        answers=questionnaire_answers,
                        outcome=outcome,
                    )
                ),
                phase_id=step.step_id,
            )
        else:
            result = runner.run_isolated_prompt(
                workflow=run.workflow_id,
                phase_label=record.label or step.step_id,
                prompt_text=prompt_text,
                preferred_model=model,
                phase_id=step.step_id,
                build_continuation=_unblock_continuation(step) if declares_outcome else None,
            )
    except Exception as error:  # noqa: BLE001
        # A sessão caiu: timeout, processo morto, protocolo quebrado. Isto
        # subia até `run_workflow` e matava a run inteira calada — logo a falha
        # que mais vale refazer, porque quase nunca é do step. Vira desfecho de
        # tentativa, e quem decide é o usuário no menu de retry.
        #
        # `Exception` e não uma lista de tipos: a lista era (Timeout, Runtime,
        # OSError), e bastava um `ValueError` vindo de um stdin já fechado para
        # a run morrer sem menu nenhum. Nada que aconteça dentro de um step
        # justifica derrubar a run sem perguntar.
        _fail(run, record)
        return FAILED, _session_error(error)

    record.acp_session_id = runner.last_session_id or record.acp_session_id
    agent_text = str(result.get("phaseSummary", ""))
    record.summary = format_summary(agent_text)

    outcome = str(result.get("outcome", ""))
    if outcome in {CANCEL, "cancelled"} or result.get("stopReason") == "cancelled":
        _fail(run, record)
        return FAILED, "step cancelado"

    if outcome == SKIP:
        record.status = SKIPPED
        record.ended_at = run_store.utc_now()
        run_store.save_step(run.id, record)
        if not cockpit:
            print_workflow_result(f"⏭  {record.label} pulado")
        return SKIPPED, ""

    if step.requires_approval and not bool(result.get("approved")):
        _fail(run, record)
        return FAILED, "step não aprovado"

    if not step.requires_approval and not _prompt_succeeded(result):
        _fail(run, record)
        return FAILED, str(result.get("stopReason") or "o agente não concluiu o step")

    repeats = False
    if declares_outcome:
        # Lido do texto cru, não de `record.summary`: o resumo é truncado no
        # fim, e é justamente no fim que o bloco de desfecho fica.
        declared = parse_outcome(agent_text)
        if not declared.delivered:
            return _block(run, record, _blocked_reason(declared))
        # `repeat_from` é a permissão, `next: repeat` é o pedido. Sem os dois, o
        # campo não quer dizer nada: um agente não cria laço onde o workflow não
        # declarou um.
        repeats = bool(step.repeat_from) and declared.repeats

    record.status = DONE
    record.ended_at = run_store.utc_now()
    run_store.save_step(run.id, record)
    if not cockpit:
        print_workflow_result(f"✓ {record.label}")
    return (REPEAT if repeats else DONE), ""


def _unblock_continuation(step: StepDef) -> Callable[..., str]:
    """A chance que o agente tem de se destravar sozinho, antes de acordar alguém.

    Boa parte do que um agente chama de bloqueio está ao alcance dele: um
    arquivo que ele podia ter criado, um caminho que ele não tentou, metade do
    workspace que ele não leu. Escalar direto para a pessoa nesses casos é
    interromper alguém por nada.

    A continuação roda **na mesma sessão** (ver `run_isolated_prompt`), então o
    agente não recomeça do zero, e é uma só por tentativa: quem repete o
    bloqueio depois de ser cutucado está dizendo que precisa de gente.

    Bloco de desfecho ausente também passa por aqui, e é o caso mais barato de
    todos — o agente costuma ter feito o trabalho e só ter esquecido de
    declarar. Sem isto, todo esquecimento viraria uma pergunta na tela.
    """
    spent = False

    def build(*, result: dict[str, Any], turn: int = 0, **_kwargs: Any) -> str:
        nonlocal spent
        if spent:
            return ""
        declared = parse_outcome(str(result.get("phaseSummary", "")))
        if declared.delivered:
            return ""
        spent = True
        if declared.status == MISSING:
            return build_outcome_reminder_prompt(step_id=step.step_id)
        if declared.needs_user:
            # O agente já disse que depende de outra pessoa: mandar tentar de
            # novo só o faria bater na mesma parede.
            return ""
        return build_unblock_prompt(step_id=step.step_id, reason=declared.reason)

    return build


def _blocked_reason(declared: Outcome) -> str:
    if declared.status == MISSING:
        return (
            "o agente encerrou sem declarar o desfecho do step — "
            "não dá para afirmar que ele entregou o que o step pede"
        )
    return declared.reason or "o agente declarou bloqueio sem dizer o motivo"


def _block(run: run_store.RunRecord, record: StepRecord, reason: str) -> tuple[str, str]:
    """Grava o step como bloqueado: rodou, não quebrou, não entregou."""
    record.status = BLOCKED
    record.ended_at = run_store.utc_now()
    run_store.save_step(run.id, record)
    return BLOCKED, reason


def _fail_running_steps(run: run_store.RunRecord) -> None:
    for record in run.steps:
        if record.status == RUNNING:
            _fail(run, record)


def _fail(run: run_store.RunRecord, record: StepRecord) -> None:
    """Grava a tentativa como falha antes de perguntar o que fazer.

    Antes o step ficava `running` no banco enquanto o menu de retry estava na
    tela, e uma queda ali (processo morto, cockpit fechado) deixava no histórico
    um step eternamente "executando" — que o Pulse então não sabia retomar nem
    refazer. Refazer volta o status para `running` em `_attempt_step`.
    """
    record.status = FAILED
    record.ended_at = run_store.utc_now()
    run_store.save_step(run.id, record)


def _context(
    run: run_store.RunRecord,
    step: StepDef,
    exec_dir: Path,
    item: Item | None = None,
) -> dict[str, str]:
    """Valores que o `prompt_template` pode citar.

    Chaves genéricas de propósito: o motor não tem nome de artefato nem de fase
    para oferecer. O que um step produziu chega no seguinte como `previous_summary`
    e `artifacts` — o resto o agente descobre lendo o workspace.

    `workspace` é onde o agente **trabalha**: o worktree da run, quando há um.
    O agente não precisa saber que existe uma raiz de projeto em outro lugar —
    para ele aquele diretório é o repositório.

    `item_*` só tem valor num step de fan-out. Fora dele são strings vazias e não
    chaves ausentes: o mesmo `prompt_template` roda nos dois modos, e chave
    ausente é `TemplateError`.

    `previous_status` acompanha `previous_summary`: é o desfecho do step de onde
    aquele texto veio (`done` ou `skipped`), não um canal novo de informação.
    Existe porque pular é uma escolha do usuário que o step seguinte precisa
    poder respeitar — sem ela, pulado e concluído chegam indistinguíveis no
    prompt do próximo. Vazio quando nenhum step anterior deixou resumo.

    O pulo pelo menu de bloqueio limpa `summary` de propósito, então aquele step
    some da varredura e o status reportado é o do anterior a ele. É o que a chave
    promete — "o que o step anterior me entregou" —, e é diferente do pulo na
    aprovação, que preserva o resumo.
    """
    artifacts = [entry["path"] for entry in run_store.list_artifacts(run.id)]
    # Irmãos do fan-out: mesmo step da definição, item diferente. Serve para o
    # prompt poder dizer "task 2 de 7" sem o motor saber o que é uma task.
    prefix = f"{step.step_id.rsplit(':', 1)[0]}:" if item is not None else ""
    siblings = (
        [record for record in run.steps if record.step_id.startswith(prefix)] if prefix else []
    )
    previous = _previous_settled(run, step.step_id)
    return {
        "user_prompt": run.user_prompt.strip(),
        "workspace": str(exec_dir),
        "workflow_id": run.workflow_id,
        "run_id": run.id,
        "step_id": step.step_id,
        "step_label": step.label,
        "previous_summary": previous.summary if previous is not None else "",
        "previous_status": previous.status if previous is not None else "",
        "artifacts": "\n".join(f"- {path}" for path in artifacts),
        "item_id": item.id if item else "",
        "item_label": item.label if item else "",
        "item_index": str(_index_of(siblings, step.step_id)) if item else "",
        "item_total": str(len(siblings)) if item else "",
    }


def _index_of(records: list[StepRecord], step_id: str) -> int:
    for index, record in enumerate(records, start=1):
        if record.step_id == step_id:
            return index
    return 1


def _activate_agent(
    runner: AcpSessionRunner,
    workspace: Path,
    step: StepDef,
    fallback_model: str | None,
) -> tuple[str | None, str]:
    """Aplica runtime/model/policy do agente do step e devolve o que falta ao prompt.

    As `instructions` do agente vão inline no prompt em vez de virar arquivo no
    disco do usuário: é o mesmo texto para qualquer runtime, e nenhum runtime
    precisa saber que o Pulse existe.
    """
    resolved = resolve_config(workspace=workspace, pulse_agent=step.agent_id)
    runner.use_agent(step.agent_id, _POLICIES.get(resolved.permission_policy, "ask"))
    definition = get_agent(step.agent_id)
    instructions = definition.instructions.strip() if definition is not None else ""
    return resolved.model or fallback_model, instructions


def _release_step(
    runner: AcpSessionRunner,
    *,
    run: run_store.RunRecord,
    record: StepRecord,
    label: str,
) -> None:
    """Solta o step cortado pela parada, devolvendo-o para pendente.

    Ele não terminou nem falhou — o usuário cortou. Pendente é o que faz
    `resume_run_id` recomeçar por ele e só por ele: os steps que já fecharam
    continuam `done`/`skipped` e não são refeitos.
    """
    if record.status in {RUNNING, FAILED, BLOCKED}:
        record.status = PENDING
        record.ended_at = ""
        run_store.save_step(run.id, record)
        _sync_steps(runner, run)
    _notify(runner, f"Run parada em {label}" if label else "Run parada pelo usuário")


def _offer_retry(runner: AcpSessionRunner, title: str, reason: str) -> tuple[str, str]:
    """Decide o que fazer com um step que falhou."""
    return _choose(
        runner,
        title,
        reason,
        [
            ("Refazer", "retry"),
            ("Outro — dizer o que fazer", "guidance"),
            ("Parar", "stop"),
        ],
    )


def _offer_blocked(runner: AcpSessionRunner, title: str, reason: str) -> tuple[str, str]:
    """Decide o que fazer com um step que o agente não teve como concluir.

    Tem uma opção a mais que o menu de falha: pular. Um bloqueio costuma ser
    legítimo — falta um acesso, falta uma decisão — e às vezes a resposta certa
    é seguir sem aquele step, o que precisa ficar registrado como `skipped` e
    não escondido num `done`.
    """
    return _choose(
        runner,
        title,
        reason,
        [
            ("Refazer — já resolvi", "retry"),
            ("Outro — dizer o que fazer", "guidance"),
            ("Pular este step", "skip"),
            ("Parar a run", "stop"),
        ],
    )


def _choose(
    runner: AcpSessionRunner,
    title: str,
    reason: str,
    choices: list[tuple[str, str]],
) -> tuple[str, str]:
    """Pergunta ao usuário e devolve `(escolha, orientação)`.

    "Outro" deixa o usuário escrever o que o agente deve fazer — nem toda falha
    se resolve repetindo a mesma tentativa.

    Sem ninguém para perguntar (CLI, cockpit fechado, run do daemon), a resposta
    é sempre parar. É a inversão que faltava: antes, o que ninguém via seguia
    adiante sozinho.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    prompt = reason.strip() or "O step não foi concluído."
    if not callable(select):
        _notify(runner, f"{title}: {prompt}")
        return "stop", ""
    choice = select(prompt, choices, title=title)
    if choice == "guidance":
        guidance = _ask_guidance(runner, title)
        if guidance:
            return "retry", guidance
        # desistiu de escrever: volta a perguntar em vez de parar por engano
        return _choose(runner, title, reason, choices)
    if choice in {value for _label, value in choices}:
        return str(choice), ""
    return "stop", ""


def _session_error(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return f"o agente parou de responder — {error}"
    if isinstance(error, RuntimeError | OSError):
        return f"a sessão do agente caiu — {error}"
    # Falha que não é de sessão: o tipo é a única pista que o usuário tem para
    # decidir entre refazer e parar.
    return f"o step quebrou — {type(error).__name__}: {error}"


def _revive_session(runner: AcpSessionRunner) -> None:
    """Reergue o processo do agente antes de refazer o step.

    Retry depois de uma sessão morta só repetiria a queda; e se reerguer também
    falhar, a próxima tentativa cai rápido e o menu volta a aparecer.
    """
    ensure = getattr(runner, "ensure_process", None)
    if not callable(ensure):
        return
    try:
        if ensure():
            _notify(runner, "Sessão do agente reiniciada")
    except (RuntimeError, TimeoutError, OSError) as error:
        _notify(runner, f"Não consegui reiniciar a sessão do agente: {error}")


def _ask_guidance(runner: AcpSessionRunner, title: str) -> str:
    handler = getattr(runner, "_prompt_handler", None)
    ask_text = getattr(handler, "ask_text", None)
    if not callable(ask_text):
        return ""
    answer = ask_text("O que o agente deve fazer nesta nova tentativa?", title=title)
    return str(answer or "").strip()


def _prompt_succeeded(result: dict[str, Any]) -> bool:
    return str(result.get("stopReason") or "") in _SUCCESS_STOPS


def _control(runner: AcpSessionRunner) -> RunControl:
    return getattr(runner, "control", None) or _NEVER_INTERRUPTED


def _notify(runner: AcpSessionRunner, message: str) -> None:
    stream = getattr(runner, "_stream", None)
    info = getattr(stream, "info", None) if stream is not None else None
    if callable(info):
        info(message)


def _sync_steps(runner: AcpSessionRunner, run: run_store.RunRecord) -> None:
    """Espelha `run_steps` no painel — a lista inteira, não só os status.

    A lista vai junto porque o fan-out a muda no meio da run: o painel montou as
    fases pela definição, e um step que virou sete precisa aparecer como sete.
    """
    stream = getattr(runner, "_stream", None)
    apply = getattr(stream, "apply_phase_statuses", None) if stream is not None else None
    if not callable(apply):
        return
    apply(
        steps=[
            {"id": item.step_id, "label": item.label, "rounds": item.rounds}
            for item in run.steps
        ],
        done_ids=[item.step_id for item in run.steps if item.status == DONE],
        skipped_ids=[item.step_id for item in run.steps if item.status == SKIPPED],
        failed_ids=[item.step_id for item in run.steps if item.status == FAILED],
        blocked_ids=[item.step_id for item in run.steps if item.status == BLOCKED],
    )
