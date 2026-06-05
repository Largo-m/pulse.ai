from __future__ import annotations

from cursor_task.executor.base import ExecutionContext
from cursor_task.executor.completion import resolve_completion


def is_unattended_execution(context: ExecutionContext) -> bool:
    return context.execution_mode == "execute"


def resolve_finished_iteration(
    context: ExecutionContext,
    *,
    combined_text: str,
) -> tuple[bool, str | None]:
    if is_unattended_execution(context):
        return resolve_completion(context)

    follow_up = context.question_handler.extract_pending_question(combined_text)
    if follow_up:
        answer = context.question_handler.prompt_user(follow_up, display=False)
        return False, answer

    ready, next_prompt = resolve_completion(context)
    if (
        not ready
        and context.artifact_writer.artifact_kind == "tasks"
        and not is_unattended_execution(context)
    ):
        breakdown = context.question_handler.extract_approval_question(combined_text)
        if breakdown:
            answer = context.question_handler.prompt_user(breakdown, display=False)
            return False, answer

    return ready, next_prompt
