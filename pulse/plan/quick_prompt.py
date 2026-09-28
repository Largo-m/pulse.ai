"""Prompts do Quick mode: plano (fase 1) e implementação (fase 2).

O texto está em `quick-plan/PHASE.md`, `quick-implement/PHASE.md` e nos
`CONTINUATION-*.md` do `quick-plan`. Fica aqui a leitura da resposta do usuário
— aprovar, migrar para o pipeline completo, reduzir escopo ou ajustar — porque
é ela que decide qual template vem a seguir.
"""

from __future__ import annotations

from pathlib import Path

from pulse.prompts.ask_question import is_free_text_answer
from pulse.prompts.templates import render_shared, render_template
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
QUICK_PLAN_REFERENCES = (
    "quick-mode.md",
    "state-management.md",
    "user-input.md",
)
QUICK_IMPLEMENT_REFERENCES = (
    "quick-mode.md",
    "coding-principles.md",
    "state-management.md",
    "user-input.md",
)
QUICK_REFERENCES = QUICK_IMPLEMENT_REFERENCES
_PLAN_MAX_CHARS = 8_000

#: Desfecho do questionário → template de continuação.
_CONTINUATION_TEMPLATES = {
    "migrate": "CONTINUATION-migrate.md",
    "reduce_scope": "CONTINUATION-reduce-scope.md",
    "adjust": "CONTINUATION-adjust.md",
}


def resolve_quick_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def format_plan_summary(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _PLAN_MAX_CHARS:
        return cleaned
    return cleaned[:_PLAN_MAX_CHARS].rstrip() + "\n\n[… plano truncado …]"


def approval_is_positive(answers_text: str) -> bool:
    answers = _quick_answers(answers_text)
    if not answers:
        return False
    for raw in answers:
        # Ver a nota em `pulse.plan.new_issue_prompt.approval_is_positive`.
        if is_free_text_answer(raw):
            continue
        answer = raw.lower()
        if any(token in answer for token in ("não", "nao", "ajuste", "cancel", "migrar", "reduzir", "pular")):
            continue
        if "aprov" in answer:
            return True
    return False


def _quick_answers(answers_text: str) -> list[str]:
    answers: list[str] = []
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            answer = line.lstrip("→").strip()
            if answer:
                answers.append(answer)
    return answers


def first_questionnaire_answer(answers_text: str) -> str:
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            return line.lstrip("→").strip()
    return ""


def classify_quick_questionnaire_outcome(answers_text: str) -> str:
    answer = first_questionnaire_answer(answers_text).lower()
    if not answer:
        return "unknown"
    if "cancelar" in answer:
        return "cancel"
    if approval_is_positive(answers_text):
        return "approve"
    if "migrar" in answer and "pipeline" in answer:
        return "migrate"
    if "quick fix:" in answer or "reduzir escopo" in answer:
        return "reduce_scope"
    if "ajuste" in answer:
        return "adjust"
    return "continue"


def _agent_block(
    *,
    skill_dir: Path,
    agent_id: str,
    references: tuple[str, ...],
    workspace: Path,
) -> str:
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Quick mode",
        references=references,
        agent_id=agent_id,
        workspace=workspace,
    )
    return "\n".join(sections).rstrip()


def build_quick_plan_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
) -> str:
    return render_template(
        "quick-plan",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Quick task",
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-short", {"workspace": str(workspace)}),
            "agent": _agent_block(
                skill_dir=skill_dir,
                agent_id="quick-plan",
                references=QUICK_PLAN_REFERENCES,
                workspace=workspace,
            ),
        },
    )


def build_quick_implement_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    plan_summary: str = "",
    approval_answers: str = "",
) -> str:
    return render_template(
        "quick-implement",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Quick task",
            "summary": format_plan_summary(plan_summary)
            or "(Re-read TASK.md under `.pulse/specs/quick/` — no summary captured from phase 1.)",
            "answers": approval_answers.strip(),
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-plan", {"workspace": str(workspace)}),
            "agent": _agent_block(
                skill_dir=skill_dir,
                agent_id="quick-implement",
                references=QUICK_IMPLEMENT_REFERENCES,
                workspace=workspace,
            ),
        },
    )


def build_quick_continuation_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    plan_summary: str,
    questionnaire_answers: str,
    outcome: str,
) -> str:
    return render_template(
        "quick-plan",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Quick task",
            "summary": format_plan_summary(plan_summary) or "(No previous summary.)",
            "answers": questionnaire_answers.strip(),
            "output_language": render_shared("output-language"),
            "agent": _agent_block(
                skill_dir=skill_dir,
                agent_id="quick-plan",
                references=QUICK_PLAN_REFERENCES,
                workspace=workspace,
            ),
        },
        name=_CONTINUATION_TEMPLATES.get(outcome, "CONTINUATION-continue.md"),
    )
