from __future__ import annotations

from pathlib import Path
from typing import Callable

from pulse.plan.specify_state import WorkflowState
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
_SUMMARY_MAX_CHARS = 8_000

PHASE_REFERENCES: dict[str, tuple[str, ...]] = {
    "specify": (
        "specify.md",
        "discuss.md",
        "state-management.md",
        "user-input.md",
    ),
    "design": (
        "design.md",
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

def resolve_new_issue_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def format_phase_summary(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _SUMMARY_MAX_CHARS:
        return cleaned
    return cleaned[:_SUMMARY_MAX_CHARS].rstrip() + "\n\n[… resumo truncado …]"


def first_questionnaire_answer(answers_text: str) -> str:
    for line in answers_text.splitlines():
        if line.strip().startswith("→"):
            return line.lstrip("→").strip()
    return ""


def approval_is_positive(answers_text: str) -> bool:
    answer = first_questionnaire_answer(answers_text).lower()
    if not answer:
        return False
    if any(token in answer for token in ("não", "nao", "ajuste", "cancel", "pular fase")):
        return False
    return "aprov" in answer or answer.startswith("a)") or "sim" in answer


def classify_phase_questionnaire_outcome(answers_text: str) -> str:
    answer = first_questionnaire_answer(answers_text).lower()
    if not answer:
        return "unknown"
    if "cancelar" in answer:
        return "cancel"
    if "pular" in answer and "fase" in answer:
        return "skip"
    if approval_is_positive(answers_text):
        return "approve"
    if "ajuste" in answer:
        return "adjust"
    return "continue"


def _isolation_block(workspace: Path) -> list[str]:
    return [
        "## Isolamento (obrigatório)",
        "",
        "Esta é uma execução **nova e isolada** do Pulse.",
        f"Analise **somente** o workspace `{workspace}`.",
        "Ignore conversas anteriores do Cursor, outros projetos e execuções passadas do Pulse.",
        "Você não tem histórico de fases anteriores — use apenas os artefatos em disco listados abaixo.",
        "",
    ]


def _approval_block(phase_label: str, artifact_path: str) -> list[str]:
    return [
        f"### Bloco de aprovação — {phase_label} (formato obrigatório)",
        "",
        "Você **não** tem ferramentas externas para perguntar. Termine a resposta com um **bloco",
        "de texto** que o Pulse renderiza no terminal, exatamente neste formato:",
        "",
        "```text",
        "Preciso de algumas informações antes de continuar.",
        f"1. Aprovar {phase_label} ({artifact_path}) e avançar?",
        "A) Sim, aprovar e continuar",
        "B) Não, preciso de ajustes (descreva)",
        "C) Cancelar workflow",
        "```",
        "",
        "PROIBIDO nesta fase:",
        "- Editar código de aplicação (apenas arquivos `.pulse/specs/` são permitidos).",
        "- Enviar qualquer texto fora do bloco ```text quando for perguntar/aprovar.",
        "- Avançar para a próxima fase sem aprovação explícita.",
        "",
    ]


def _workflow_state_instructions(state: WorkflowState) -> list[str]:
    workflow_rel = state.workflow_path.as_posix()
    return [
        "## Estado do workflow (obrigatório)",
        "",
        f"Atualize `{workflow_rel}` após concluir esta fase:",
        "",
        f"- `feature_slug`: `{state.feature_slug}`",
        f"- `complexity`: avalie (small/medium/large/complex)",
        f"- `current_phase`: fase atual",
        "- `phases.<fase>.status`: `awaiting_approval` ao terminar",
        "- `phases.design.skip` / `phases.tasks.skip`: `true` quando a fase não for necessária",
        "- `phases.<fase>.skip_reason`: motivo quando skip=true",
        "",
        "O Pulse lê este arquivo para decidir a próxima fase. Mantenha-o consistente.",
        "",
    ]


def build_specify_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    feature_dir = (workspace / state.feature_dir).as_posix()
    sections = [
        f"Workspace: `{workspace}`",
        f"Feature slug: `{state.feature_slug}`",
        f"Diretório da feature: `{feature_dir}`",
        f"Tarefa do usuário: {user_prompt.strip() or 'Nova funcionalidade'}",
        "",
    ]
    sections.extend(_isolation_block(workspace))
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Specify",
        references=PHASE_REFERENCES["specify"],
    )
    sections.extend(_workflow_state_instructions(state))
    sections.extend(
        [
            "## Fase Specify — capturar O QUÊ construir (SEM implementar)",
            "",
            "Siga `specify.md` e `SKILL.md` (auto-sizing por complexidade).",
            "O ACP já carrega rules/skills do workspace; não reler o conjunto por rotina.",
            "",
            "1. Garanta que `.pulse/specs/project/STATE.md` exista.",
            f"2. Crie `{feature_dir}/spec.md` com requirements rastreáveis.",
            "3. Se houver áreas cinzentas, crie `context.md` conforme `discuss.md`.",
            f"4. Atualize `{state.workflow_path.as_posix()}`:",
            "   - Defina `complexity`",
            "   - Marque `phases.specify.status: awaiting_approval`",
            "   - Se Design não for necessário: `phases.design.skip: true` + `skip_reason`",
            "   - Se Tasks não for necessário: `phases.tasks.skip: true` + `skip_reason`",
            "5. Atualize `STATE.md` → Current Work com esta feature.",
            "",
            "Apresente resumo curto: problema, escopo, complexidade, fases que serão puladas.",
            "",
        ]
    )
    sections.extend(_approval_block("Specify", f"{feature_dir}/spec.md"))
    sections.append("Responda em português.")
    sections.append("")
    return "\n".join(sections)


def build_design_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    feature_dir = (workspace / state.feature_dir).as_posix()
    sections = [
        f"Workspace: `{workspace}`",
        f"Feature: `{state.feature_slug}`",
        f"Tarefa original: {user_prompt.strip()}",
        "",
    ]
    sections.extend(_isolation_block(workspace))
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Design",
        references=PHASE_REFERENCES["design"],
    )
    sections.extend(_workflow_state_instructions(state))
    sections.extend(
        [
            "## Fase Design — definir COMO construir (SEM implementar)",
            "",
            f"Leia `{feature_dir}/spec.md` (e `context.md` se existir).",
            f"Crie `{feature_dir}/design.md` conforme `design.md`.",
            "Leia rules/conventions no disco só se forem necessárias para decisões de arquitetura.",
            f"Atualize `{state.workflow_path.as_posix()}`:",
            "   - `phases.design.status: awaiting_approval`",
            "   - `current_phase: design`",
            "",
            "Apresente resumo: arquitetura, componentes, reuso de código existente.",
            "",
        ]
    )
    sections.extend(_approval_block("Design", f"{feature_dir}/design.md"))
    sections.append("Responda em português.")
    sections.append("")
    return "\n".join(sections)


def build_tasks_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    feature_dir = (workspace / state.feature_dir).as_posix()
    sections = [
        f"Workspace: `{workspace}`",
        f"Feature: `{state.feature_slug}`",
        f"Tarefa original: {user_prompt.strip()}",
        "",
    ]
    sections.extend(_isolation_block(workspace))
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Tasks",
        references=PHASE_REFERENCES["tasks"],
    )
    sections.extend(_workflow_state_instructions(state))
    sections.extend(
        [
            "## Fase Tasks — quebrar em tarefas atômicas (SEM implementar)",
            "",
            f"Leia `{feature_dir}/spec.md`",
            f"Leia `{feature_dir}/design.md` se existir",
            f"Crie `{feature_dir}/tasks.md` conforme `tasks.md` (T1, T2, … com Depends on).",
            "O ACP já carrega rules/skills do workspace; não reler o conjunto por rotina.",
            f"Atualize `{state.workflow_path.as_posix()}`:",
            "   - `phases.tasks.status: awaiting_approval`",
            "   - `current_phase: tasks`",
            "   - Popule `tasks` com lista `[{id: T1, title: ...}, ...]` na ordem de execução",
            "",
            "Execute os 3 checks obrigatórios de `tasks.md` antes de apresentar.",
            "Apresente resumo: contagem de tasks, fases de execução, dependências críticas.",
            "",
        ]
    )
    sections.extend(_approval_block("Tasks", f"{feature_dir}/tasks.md"))
    sections.append("Responda em português.")
    sections.append("")
    return "\n".join(sections)


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
    feature_dir = (workspace / state.feature_dir).as_posix()
    ids_joined = ", ".join(task_ids)
    sections = [
        f"Workspace: `{workspace}`",
        f"Feature: `{state.feature_slug}`",
        f"Tarefa original: {user_prompt.strip()}",
        f"Task atual: **{wave_label}**",
        f"Task: {ids_joined}",
        "",
    ]
    sections.extend(_isolation_block(workspace))
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Execute",
        references=PHASE_REFERENCES["execute"],
    )
    sections.extend(
        [
            "## Fase Execute — implementar task",
            "",
            f"Leia `{feature_dir}/spec.md`",
        ]
    )
    if not state.phases["design"].skip:
        sections.append(f"Leia `{feature_dir}/design.md` se existir")
    if not tasks_skipped:
        sections.extend(
            [
                f"Leia `{feature_dir}/tasks.md` — implemente **somente** esta task:",
                "",
                *task_lines,
                "",
                "Plano → implementar → verificar o Done when da task.",
                "Marque a task concluída em `tasks.md` após a verificação.",
                "",
            ]
        )
    else:
        sections.extend(
            [
                "Não há `tasks.md` — siga o plano inline de `implement.md` para esta execução.",
                "",
            ]
        )
    sections.extend(
        [
            f"Atualize `{state.workflow_path.as_posix()}`:",
            "   - `current_task_id`: esta task",
            "   - **Não** marque `status: done` nas tasks — o Pulse valida os gates e marca done depois",
            "",
            "Siga `implement.md` para esta task.",
            "Não implemente outras tasks.",
            "Não execute operações de git.",
            "Responda em português.",
            "",
        ]
    )
    return "\n".join(sections)


def build_execute_inline_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    state: WorkflowState,
) -> str:
    feature_dir = (workspace / state.feature_dir).as_posix()
    sections = [
        f"Workspace: `{workspace}`",
        f"Feature: `{state.feature_slug}`",
        f"Tarefa original: {user_prompt.strip()}",
        "",
    ]
    sections.extend(_isolation_block(workspace))
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Execute",
        references=PHASE_REFERENCES["execute"],
    )
    sections.extend(
        [
            "## Fase Execute — implementação (tasks implícitas)",
            "",
            f"Leia `{feature_dir}/spec.md`",
            f"Leia `{feature_dir}/design.md` se existir",
            "",
            "A fase Tasks foi pulada — liste passos atômicos inline conforme `implement.md`",
            "antes de escrever código. Se >5 passos, pare e documente que tasks.md é necessário.",
            "",
            f"Atualize `{state.workflow_path.as_posix()}`:",
            "   - `phases.execute.status: done` ao concluir",
            "",
            "Implemente, verifique e atualize STATE.md.",
            "Não execute operações de git.",
            "Responda em português.",
            "",
        ]
    )
    return "\n".join(sections)


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
    summary = format_phase_summary(phase_summary)
    sections = [
        f"Continue a fase **{phase}** com base na escolha do usuário.",
        f"Workspace: `{workspace}`",
        f"Feature: `{state.feature_slug}`",
        f"Tarefa original: {user_prompt.strip()}",
        "",
        "## Resposta do usuário (autoritativa)",
        "",
        questionnaire_answers.strip(),
        "",
        "## Análise anterior",
        "",
        summary or "(Sem resumo anterior.)",
        "",
    ]
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow=phase.capitalize(),
        references=PHASE_REFERENCES.get(phase, ()),
    )

    if outcome == "adjust":
        sections.extend(
            [
                "O usuário pediu **ajustes** antes de aprovar.",
                "Atualize os artefatos da fase e reapresente o resumo com novo bloco de aprovação.",
                "Não avance para a próxima fase.",
                "Responda em português.",
                "",
            ]
        )
    else:
        sections.extend(
            [
                "Prossiga conforme a escolha do usuário e as regras da fase.",
                "Responda em português.",
                "",
            ]
        )

    sections.append(
        "Relembre: ao terminar, atualize workflow.yaml e termine com bloco de aprovação CLI."
    )
    sections.append("")
    _ = prompt_builder
    return "\n".join(sections)
