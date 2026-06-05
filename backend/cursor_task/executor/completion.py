from __future__ import annotations

from cursor_task.executor.base import ExecutionContext
from cursor_task.task_tracker import is_task_completed

APPROVAL_REQUIRED_PROMPT = (
    "O documento foi gravado antes da aprovação do usuário. "
    "Apresente o rascunho para revisão com as opções A/B/C/D da skill e aguarde aprovação explícita."
)

MISSING_SAVE_AFTER_APPROVAL = (
    "O usuário aprovou o rascunho. Salve o artefato final no caminho indicado pela skill."
)

MISSING_SAVE_AFTER_TASKS_APPROVAL = (
    "O usuário aprovou o breakdown de tasks. "
    "Gere `_tasks.md`, os arquivos `task_NN.md` e enriqueça cada task conforme a skill."
)

MISSING_EXECUTE_TASK_COMPLETION = (
    "A implementação parece concluída, mas o tracking não reflete completion. "
    "Atualize checkboxes e status no task file e em `_tasks.md` conforme a skill execute-task."
)


def resolve_completion(context: ExecutionContext) -> tuple[bool, str | None]:
    if context.execution_mode == "execute":
        return _resolve_execute_completion(context)

    artifact_kind = context.artifact_writer.artifact_kind

    if context.awaiting_post_approval:
        if context.artifact_writer.has_artifact_on_disk():
            return True, None
        if artifact_kind == "tasks":
            return False, MISSING_SAVE_AFTER_TASKS_APPROVAL
        return False, MISSING_SAVE_AFTER_APPROVAL

    if context.artifact_writer.has_artifact_on_disk():
        return False, APPROVAL_REQUIRED_PROMPT

    return False, None


def _resolve_execute_completion(context: ExecutionContext) -> tuple[bool, str | None]:
    task_file = context.execute_task_file
    master_tasks_file = context.execute_master_tasks_file
    task_number = context.execute_task_number

    if task_file is None or master_tasks_file is None or task_number is None:
        raise ValueError("contexto execute incompleto: task file, master file ou número ausente")

    if is_task_completed(
        task_file=task_file,
        master_tasks_file=master_tasks_file,
        task_number=task_number,
    ):
        return True, None

    return False, MISSING_EXECUTE_TASK_COMPLETION
