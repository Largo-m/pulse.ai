"""Monta os prompts do pipeline PRD → Techspec → Tasks → Execute.

O texto vive em `PHASE.md` / `CONTINUATION-*.md` dentro da pasta de cada agente
([pulse.prompts.templates]) — editável pelo usuário. O que fica aqui é regra do
Pulse: qual template a fase usa, que valores ele recebe, e como ler o que o
agente respondeu (aprovou, pediu ajuste, cancelou).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pulse.plan.workflow_state import WorkflowState
from pulse.prompts.ask_question import is_free_text_answer
from pulse.prompts.templates import render_shared, render_template
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
_SUMMARY_MAX_CHARS = 8_000

PHASE_REFERENCES: dict[str, tuple[str, ...]] = {
    "prd": (
        "prd.md",
        "discuss.md",
        "state-management.md",
        "user-input.md",
    ),
    "techspec": (
        "techspec.md",
        "state-management.md",
        "user-input.md",
    ),
    "tasks": (
        "tasks.md",
        "state-management.md",
        "user-input.md",
    ),
    "execute": (
        "implement.md",
        "validate.md",
        "coding-principles.md",
        "state-management.md",
    ),
}

#: Agente responsável por cada fase. Os templates moram na pasta dele.
PHASE_AGENTS = {
    "prd": "prd",
    "techspec": "techspec",
    "tasks": "tasks",
    "execute": "implement",
}

_PHASE_LABELS = {"prd": "PRD", "techspec": "Techspec", "tasks": "Tasks"}
_PHASE_ARTIFACTS = {"prd": "PRD.md", "techspec": "TECHSPEC.md", "tasks": "tasks.md"}

#: O PRD só pode fechar com aprovação quando o ledger estiver limpo.
_PRD_APPROVAL_CONDITION = "nothing is left open: the ledger has no `open` and no `assumed` row"


def resolve_new_issue_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def format_phase_summary(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _SUMMARY_MAX_CHARS:
        return cleaned
    return cleaned[:_SUMMARY_MAX_CHARS].rstrip() + "\n\n[… summary truncated …]"


def first_questionnaire_answer(answers_text: str) -> str:
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            return line.lstrip("→").strip()
    return ""


def _questionnaire_answers(answers_text: str) -> list[str]:
    answers: list[str] = []
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            answer = line.lstrip("→").strip()
            if answer:
                answers.append(answer)
    return answers


def approval_is_positive(answers_text: str) -> bool:
    answers = _questionnaire_answers(answers_text)
    if not answers:
        return False
    for raw in answers:
        # Texto livre é orientação, não escolha: "revise o fluxo de aprovação"
        # não pode aprovar a fase só porque contém "aprov".
        if is_free_text_answer(raw):
            continue
        answer = raw.lower()
        if any(token in answer for token in ("não", "nao", "ajuste", "cancel", "pular")):
            continue
        if "aprov" in answer:
            return True
    return False


def classify_phase_questionnaire_outcome(answers_text: str) -> str:
    answers = [answer.lower() for answer in _questionnaire_answers(answers_text)]
    if not answers:
        return "unknown"
    if any("cancelar" in answer for answer in answers):
        return "cancel"
    if any("pular" in answer and "fase" in answer for answer in answers):
        return "skip"
    if approval_is_positive(answers_text):
        return "approve"
    if any("ajuste" in answer for answer in answers):
        return "adjust"
    return "continue"


def _agent_block(
    *,
    skill_dir: Path,
    workflow: str,
    references: tuple[str, ...],
    agent_id: str,
    workspace: Path,
) -> str:
    """Playbook do agente (AGENT.md) ou, sem ele, a lista de references."""
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow=workflow,
        references=references,
        agent_id=agent_id,
        workspace=workspace,
    )
    return "\n".join(sections).rstrip()


def _base_context(
    *,
    workspace: Path,
    user_prompt: str,
    state: WorkflowState,
) -> dict[str, str]:
    workspace_text = str(workspace)
    return {
        "workspace": workspace_text,
        "user_prompt": user_prompt.strip(),
        "feature_slug": state.feature_slug,
        "feature_dir": (workspace / state.feature_dir).as_posix(),
        "workflow_path": state.workflow_path.as_posix(),
        "isolation": render_shared("isolation", {"workspace": workspace_text}),
        "workflow_state": render_shared(
            "workflow-state",
            {"feature_slug": state.feature_slug, "workflow_path": state.workflow_path.as_posix()},
        ),
        # Instruções em inglês, artefatos em pt-BR: a regra precisa viajar com
        # todo prompt, porque é o texto que o agente vai escrever no disco.
        "output_language": render_shared("output-language"),
    }


def _approval(phase: str, artifact_path: str, *, condition: str = "") -> str:
    label = _PHASE_LABELS.get(phase, phase.capitalize())
    values = {"phase_label": label, "artifact_path": artifact_path}
    if condition:
        return render_shared("approval-conditional", {**values, "condition": condition})
    return render_shared("approval", values)


def _phase_context(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    phase: str,
) -> dict[str, str]:
    agent_id = PHASE_AGENTS[phase]
    feature_dir = (workspace / state.feature_dir).as_posix()
    artifact = _PHASE_ARTIFACTS.get(phase, "")
    context = _base_context(workspace=workspace, user_prompt=user_prompt, state=state)
    context["agent"] = _agent_block(
        skill_dir=skill_dir,
        workflow=_PHASE_LABELS.get(phase, phase.capitalize()),
        references=PHASE_REFERENCES[phase],
        agent_id=agent_id,
        workspace=workspace,
    )
    if artifact:
        condition = _PRD_APPROVAL_CONDITION if phase == "prd" else ""
        context["approval"] = _approval(phase, f"{feature_dir}/{artifact}", condition=condition)
    if phase == "prd":
        context["clarify"] = render_shared("clarify")
    return context


def build_prd_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    context = _phase_context(
        workspace=workspace,
        user_prompt=user_prompt or "New feature",
        skill_dir=skill_dir,
        state=state,
        phase="prd",
    )
    return render_template("prd", context)


def build_techspec_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    context = _phase_context(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
        phase="techspec",
    )
    return render_template("techspec", context)


def build_tasks_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    context = _phase_context(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
        phase="tasks",
    )
    return render_template("tasks", context)


def build_execute_task_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    task_id: str,
    task_title: str,
    tasks_skipped: bool,
) -> str:
    return build_execute_wave_prompt(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
        wave_label=f"Task {task_id}",
        task_lines=[f"- **{task_id}** — {task_title}"],
        task_ids=[task_id],
        parallel=False,
        tasks_skipped=tasks_skipped,
    )


def build_execute_wave_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    wave_label: str,
    task_lines: list[str],
    task_ids: list[str],
    parallel: bool = False,
    tasks_skipped: bool,
) -> str:
    context = _phase_context(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
        phase="execute",
    )
    context.update(
        {
            "wave_label": wave_label,
            "task_ids": ", ".join(task_ids),
            "task_list": "\n".join(task_lines),
            "techspec_line": (
                ""
                if state.phases["techspec"].skip
                else f"Read `{context['feature_dir']}/TECHSPEC.md` if it exists"
            ),
        }
    )
    # Sem tasks.md não há task a citar: o agente segue o plano inline.
    name = "PHASE-INLINE.md" if tasks_skipped else "PHASE.md"
    return render_template("implement", context, name=name)


def build_execute_inline_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    context = _phase_context(
        workspace=workspace,
        user_prompt=user_prompt,
        skill_dir=skill_dir,
        state=state,
        phase="execute",
    )
    return render_template("implement", context, name="PHASE-INLINE.md")


def build_phase_continuation_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
    phase: str,
    phase_summary: str,
    questionnaire_answers: str,
    outcome: str,
    prompt_builder: Callable[..., str],
) -> str:
    agent_id = PHASE_AGENTS.get(phase, "implement")
    context = _base_context(workspace=workspace, user_prompt=user_prompt, state=state)
    context.update(
        {
            "phase": phase,
            "summary": format_phase_summary(phase_summary) or "(No previous summary.)",
            "answers": questionnaire_answers.strip(),
            "agent": _agent_block(
                skill_dir=skill_dir,
                workflow=phase.capitalize(),
                references=PHASE_REFERENCES.get(phase, ()),
                agent_id=agent_id,
                workspace=workspace,
            ),
        }
    )
    # `adjust` e `continue` pedem coisas diferentes do agente; os demais desfechos
    # (approve/cancel/skip) nunca chegam aqui — o flow trata antes.
    name = "CONTINUATION-adjust.md" if outcome == "adjust" else "CONTINUATION-continue.md"
    _ = prompt_builder
    return render_template(agent_id, context, name=name)
