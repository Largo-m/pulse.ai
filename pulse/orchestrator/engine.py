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
from pathlib import Path
from typing import Any

from pulse.acp.session_runner import AcpSessionRunner
from pulse.config import resolve_config
from pulse.doctor.checks import check_runtime_ready
from pulse.orchestrator.cli_output import (
    print_workflow_banner,
    print_workflow_error,
    print_workflow_result,
)
from pulse.orchestrator.fanout import Item, parse_items
from pulse.orchestrator.prompts import build_continuation_prompt, guidance_block
from pulse.ports import NullPromptPort, NullStreamSink
from pulse.prompts.approval import CANCEL, SKIP, format_summary
from pulse.prompts.permission import PermissionPolicy
from pulse.prompts.render import TemplateError, render
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.runtime.tty import is_cockpit_stream, is_interactive
from pulse.runtimes import get_runtime
from pulse.store import runs as run_store
from pulse.store.runs import DONE, FAILED, PENDING, RUNNING, SETTLED, SKIPPED, StepRecord
from pulse.store.workflow_defs import StepDef, WorkflowDef, get_agent, get_workflow

_SUCCESS_STOPS = frozenset({"end_turn", "end", "stop"})
_POLICIES: dict[str, PermissionPolicy] = {
    "ask": "ask",
    "auto_approve": "auto_approve",
    "deny_writes": "deny_writes",
}
#: Fallback para runner sem controle (CLI, testes): nunca pausa nem para.
_NEVER_INTERRUPTED = RunControl()
#: Espaço entre as posições da definição, para o fan-out caber no meio sem
#: renumerar o resto: o step 4 vira 4001, 4002… e continua antes do step 5.
POSITION_STRIDE = 1000


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
    restart: bool = False,
    control: RunControl | None = None,
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
        restart=restart,
    )

    if render_header and not cockpit:
        print_workflow_banner(
            title=definition.label,
            lines=[
                f"Workspace: {workspace_root}",
                f"Run: {run.id}",
                f"Steps: {len(run.steps)}",
                f"Tarefa: {run.user_prompt.strip() or '—'}",
            ],
        )

    runner = AcpSessionRunner(
        resolved.acp_command,
        cwd=str(workspace_root),
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
            fallback_model=resolved.model,
        )
    except (RuntimeError, TimeoutError, OSError) as error:
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
    restart: bool,
) -> run_store.RunRecord:
    if resume_run_id:
        existing = run_store.load_run(resume_run_id)
        if existing is not None:
            if restart:
                run_store.reset_steps(existing.id)
                reloaded = run_store.load_run(existing.id)
                if reloaded is not None:
                    return reloaded
            return existing
    return run_store.create_run(
        run_id=str(uuid.uuid4()),
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


def _execute(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    definition: WorkflowDef,
    run: run_store.RunRecord,
    workspace: Path,
    fallback_model: str | None,
) -> int:
    runner.start()
    try:
        runner.initialize()
        runner.authenticate()
        _sync_steps(runner, run)

        for definition_step in definition.steps:
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

                # Pausa pedida entre dois steps: segura aqui, sem nada em voo.
                if not _control(runner).checkpoint():
                    _notify(runner, "Run parada pelo usuário")
                    run_store.update_run(run.id, status="stopped")
                    return RUN_STOPPED

                run_store.update_run(run.id, status=RUNNING, current_step=step.step_id)
                exit_code = _run_step(
                    runner=runner,
                    cockpit=cockpit,
                    run=run,
                    step=step,
                    record=record,
                    workspace=workspace,
                    fallback_model=fallback_model,
                    item=item,
                )
                _sync_steps(runner, run)
                if exit_code != 0:
                    run_store.update_run(
                        run.id,
                        status="stopped" if exit_code == RUN_STOPPED else FAILED,
                    )
                    return exit_code

        run_store.update_run(run.id, status="completed")
        if not cockpit:
            print_workflow_result(f"✓ {definition.label} concluído")
        return 0
    finally:
        runner.close()


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
            run.steps.insert(
                at + index - 1,
                StepRecord(
                    step_id=step_id,
                    position=position,
                    label=label,
                    agent_id=step.agent_id,
                ),
            )
    return units


def _previous_summary(run: run_store.RunRecord, step_id: str) -> str:
    """Resumo do último step com resposta antes deste."""
    previous = ""
    for record in run.steps:
        if record.step_id == step_id:
            break
        if record.summary:
            previous = record.summary
    return previous


def _run_step(
    *,
    runner: AcpSessionRunner,
    cockpit: bool,
    run: run_store.RunRecord,
    step: StepDef,
    record: StepRecord,
    workspace: Path,
    fallback_model: str | None,
    item: Item | None = None,
) -> int:
    guidance = ""
    while True:
        outcome, reason = _attempt_step(
            runner=runner,
            cockpit=cockpit,
            run=run,
            step=step,
            record=record,
            workspace=workspace,
            fallback_model=fallback_model,
            guidance=guidance,
            item=item,
        )
        if outcome in {DONE, SKIPPED}:
            return 0

        # O step não terminou porque o usuário cortou, não porque falhou: não
        # faz sentido perguntar "quer tentar de novo?" — é só segurar e refazer.
        if _control(runner).interrupted:
            if not _hold_for_pause(runner, run=run, record=record, label=record.label):
                return RUN_STOPPED
            continue

        choice, guidance = _offer_retry(runner, f"Step {record.label} falhou", reason)
        if choice != "retry":
            record.status = FAILED
            record.ended_at = run_store.utc_now()
            run_store.save_step(run.id, record)
            return 1
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
    fallback_model: str | None,
    guidance: str,
    item: Item | None = None,
) -> tuple[str, str]:
    record.status = RUNNING
    record.started_at = record.started_at or run_store.utc_now()
    run_store.save_step(run.id, record)

    model, instructions = _activate_agent(runner, workspace, step, fallback_model)
    try:
        prompt_text = render(step.prompt_template, _context(run, step, workspace, item))
    except TemplateError as error:
        return FAILED, str(error)
    if instructions:
        prompt_text = f"{instructions}\n\n---\n\n{prompt_text}"
    prompt_text += guidance_block(guidance)

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
            )
    except (TimeoutError, RuntimeError, OSError) as error:
        # A sessão caiu: timeout, processo morto, protocolo quebrado. Isto
        # subia até `run_workflow` e matava a run inteira calada — logo a falha
        # que mais vale refazer, porque quase nunca é do step. Vira desfecho de
        # tentativa, e quem decide é o usuário no menu de retry.
        run_store.save_step(run.id, record)
        return FAILED, _session_error(error)

    record.acp_session_id = runner.last_session_id or record.acp_session_id
    record.summary = format_summary(str(result.get("phaseSummary", "")))

    outcome = str(result.get("outcome", ""))
    if outcome in {CANCEL, "cancelled"} or result.get("stopReason") == "cancelled":
        run_store.save_step(run.id, record)
        return FAILED, "step cancelado"

    if outcome == SKIP:
        record.status = SKIPPED
        record.ended_at = run_store.utc_now()
        run_store.save_step(run.id, record)
        if not cockpit:
            print_workflow_result(f"⏭  {record.label} pulado")
        return SKIPPED, ""

    if step.requires_approval and not bool(result.get("approved")):
        run_store.save_step(run.id, record)
        return FAILED, "step não aprovado"

    if not step.requires_approval and not _prompt_succeeded(result):
        run_store.save_step(run.id, record)
        return FAILED, str(result.get("stopReason") or "o agente não concluiu o step")

    record.status = DONE
    record.ended_at = run_store.utc_now()
    run_store.save_step(run.id, record)
    if not cockpit:
        print_workflow_result(f"✓ {record.label}")
    return DONE, ""


def _context(
    run: run_store.RunRecord,
    step: StepDef,
    workspace: Path,
    item: Item | None = None,
) -> dict[str, str]:
    """Valores que o `prompt_template` pode citar.

    Chaves genéricas de propósito: o motor não tem nome de artefato nem de fase
    para oferecer. O que um step produziu chega no seguinte como `previous_summary`
    e `artifacts` — o resto o agente descobre lendo o workspace.

    `item_*` só tem valor num step de fan-out. Fora dele são strings vazias e não
    chaves ausentes: o mesmo `prompt_template` roda nos dois modos, e chave
    ausente é `TemplateError`.
    """
    artifacts = [entry["path"] for entry in run_store.list_artifacts(run.id)]
    # Irmãos do fan-out: mesmo step da definição, item diferente. Serve para o
    # prompt poder dizer "task 2 de 7" sem o motor saber o que é uma task.
    prefix = f"{step.step_id.rsplit(':', 1)[0]}:" if item is not None else ""
    siblings = (
        [record for record in run.steps if record.step_id.startswith(prefix)] if prefix else []
    )
    return {
        "user_prompt": run.user_prompt.strip(),
        "workspace": str(workspace),
        "workflow_id": run.workflow_id,
        "run_id": run.id,
        "step_id": step.step_id,
        "step_label": step.label,
        "previous_summary": _previous_summary(run, step.step_id),
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


def _hold_for_pause(
    runner: AcpSessionRunner,
    *,
    run: run_store.RunRecord,
    record: StepRecord,
    label: str,
) -> bool:
    """Segura o fluxo enquanto a run está pausada.

    O step que foi cortado volta para pendente: ele não terminou, então será
    refeito inteiro ao retomar. Devolve `False` quando a run foi parada.
    """
    if record.status == RUNNING:
        record.status = PENDING
        run_store.save_step(run.id, record)
        _sync_steps(runner, run)
    if _control(runner).stopped:
        _notify(runner, f"Run parada em {label}" if label else "Run parada pelo usuário")
        return False
    _notify(runner, f"Pausado em {label}" if label else "Run pausada")
    if not _control(runner).wait_while_paused():
        _notify(runner, "Run parada pelo usuário")
        return False
    _notify(runner, f"Retomando {label}" if label else "Retomando a run")
    return True


def _offer_retry(runner: AcpSessionRunner, title: str, reason: str) -> tuple[str, str]:
    """Decide o que fazer com um step que falhou.

    Devolve `(escolha, orientação)`. "Outro" deixa o usuário escrever o que o
    agente deve fazer — nem toda falha se resolve repetindo a mesma tentativa.
    """
    handler = getattr(runner, "_prompt_handler", None)
    select = getattr(handler, "select_choice", None)
    prompt = reason.strip() or "O step não foi concluído."
    if not callable(select):
        _notify(runner, f"{title}: {prompt}")
        return "stop", ""
    choice = select(
        prompt,
        [
            ("Refazer", "retry"),
            ("Outro — dizer o que fazer", "guidance"),
            ("Parar", "stop"),
        ],
        title=title,
    )
    if choice == "retry":
        return "retry", ""
    if choice == "guidance":
        guidance = _ask_guidance(runner, title)
        if guidance:
            return "retry", guidance
        # desistiu de escrever: volta a perguntar em vez de parar por engano
        return _offer_retry(runner, title, reason)
    return "stop", ""


def _session_error(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return f"o agente parou de responder — {error}"
    return f"a sessão do agente caiu — {error}"


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
        steps=[{"id": item.step_id, "label": item.label} for item in run.steps],
        done_ids=[item.step_id for item in run.steps if item.status == DONE],
        skipped_ids=[item.step_id for item in run.steps if item.status == SKIPPED],
        failed_ids=[item.step_id for item in run.steps if item.status == FAILED],
    )
