from __future__ import annotations

from pathlib import Path

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
    answers = [answer.lower() for answer in _quick_answers(answers_text)]
    if not answers:
        return False
    for answer in answers:
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


def build_quick_plan_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
) -> str:
    sections = [
        f"Workspace: `{workspace}`",
        f"Tarefa do usuário: {user_prompt.strip() or 'Tarefa rápida'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        "Esta é uma execução **nova e isolada** do Pulse.",
        f"Analise **somente** o workspace `{workspace}`.",
        "Ignore conversas anteriores do Cursor, outros projetos e execuções passadas do Pulse.",
        "",
    ]
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Quick mode",
        references=QUICK_PLAN_REFERENCES,
        agent_id="quick-plan",
        workspace=workspace,
    )
    sections.extend(
        [
            "## Fase 1 — Verificar escopo e planejar (SEM implementar)",
            "",
            "Você está conectado ao cliente **Pulse**.",
            "Pesquise e leia arquivos para localizar onde a mudança vive.",
            "**Não edite código de aplicação nesta fase** — apenas planeje e crie arquivos em `.pulse/specs/`.",
            "O ACP já carrega rules/skills do workspace; não reler o conjunto por rotina.",
            "",
            "### 1. Elegibilidade de escopo (verifique PRIMEIRO)",
            "",
            "Siga **Scope Eligibility** de `quick-mode.md`. Se **qualquer** desqualificador se aplicar",
            "(>3 arquivos, escopo ambíguo, decisão de arquitetura, nova dependência, >1h, nova",
            "feature/multi-story, mudança arquitetural):",
            "",
            "- **Não** crie `.pulse/specs/quick/NNN-slug/TASK.md`.",
            "- **Não** implemente código de aplicação.",
            "- Explique **por que** excede o Quick Mode (concreto: contagem de arquivos, ambiguidade…).",
            "- Termine a resposta **apenas** com o bloco de perguntas de migração de pipeline (abaixo).",
            "",
            "#### Bloco de migração (escolhas fechadas — obrigatório quando fora do escopo)",
            "",
            "- **Não** use opções com \"descreva\" ou texto livre.",
            "- **Não** inclua \"Outro\" — o Pulse não adicionará opção livre neste bloco.",
            "- Opção **A:** migrar para o pipeline completo (Specify → … → Execute).",
            "- Opções **B, C, D…:** quick fixes **pré-definidos** derivados da análise do código",
            "  (uma linha cada: o quê, quais arquivos, como verificar). Cada um deve caber no Quick Mode.",
            "- Última opção: **Cancelar**.",
            "",
            "Exemplo:",
            "```text",
            "Preciso de algumas informações antes de continuar.",
            "1. Este pedido excede o Quick mode: [motivo]. Como deseja prosseguir?",
            "A) Migrar para o pipeline completo (Specify → Design → Tasks → Execute)",
            "B) Quick fix: reutilizar TokenResponseAdapter no RefreshTokenInterceptor",
            "C) Quick fix: adicionar testes unitários do RefreshTokenInterceptor",
            "D) Cancelar",
            "```",
            "",
            "### 2. Se estiver dentro do escopo — criar spec ANTES de pedir aprovação",
            "",
            "1. Garanta que `.pulse/specs/project/STATE.md` exista (crie a partir de `state-management.md` se faltar).",
            "2. Escolha o próximo `NNN` varrendo `.pulse/specs/quick/` (001, 002, …).",
            "3. Crie `.pulse/specs/quick/NNN-slug/TASK.md` com **Status: Awaiting Approval** (template de `quick-mode.md`).",
            "4. Atualize `STATE.md` → **Current Work:** `Quick NNN-slug` e adicione a linha em Quick Tasks com ⏳ Awaiting Approval.",
            "",
            "Depois, apresente um resumo curto no chat com o caminho do TASK.md, arquivos a tocar,",
            "abordagem (uma frase) e como verificar.",
            "",
            "### 3. Bloco de aprovação (formato obrigatório)",
            "",
            "Você **não** tem ferramentas externas para perguntar. Termine a resposta com um **bloco",
            "de texto** que o Pulse renderiza no terminal, exatamente neste formato:",
            "",
            "```text",
            "Preciso de algumas informações antes de continuar.",
            "1. Aprovar quick task NNN e implementar?",
            "A) Sim, aprovar e implementar",
            "B) Não, preciso de ajustes (descreva)",
            "```",
            "",
            "PROIBIDO nesta fase:",
            "- Editar código de aplicação (apenas arquivos `.pulse/specs/` são permitidos).",
            "- Enviar qualquer texto fora do bloco ```text quando for perguntar/aprovar.",
            "- Implementar antes da aprovação explícita.",
            "- Ler `.pulse/skills/` legado (entrevistas).",
            "",
            "Responda em português.",
            "",
        ]
    )

    return "\n".join(sections)


def build_quick_implement_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    plan_summary: str = "",
    approval_answers: str = "",
) -> str:
    summary = format_plan_summary(plan_summary)
    answers = approval_answers.strip()
    sections = [
        "Fase 2 do Quick Mode — implementar a quick task **aprovada**.",
        f"Workspace: `{workspace}`",
        f"Tarefa: {user_prompt.strip() or 'Tarefa rápida'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        f"Use **somente** o workspace `{workspace}` e o plano desta execução abaixo.",
        "Não reutilize conversas anteriores, outros repositórios ou execuções passadas do Pulse.",
        "",
    ]
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Quick mode",
        references=QUICK_IMPLEMENT_REFERENCES,
        agent_id="quick-implement",
        workspace=workspace,
    )
    sections.extend(
        [
            "## Plano desta execução (fase 1)",
            "",
            summary or "(Releia o TASK.md em `.pulse/specs/quick/` — nenhum resumo capturado da fase 1.)",
            "",
        ]
    )

    if answers:
        sections.extend(
            [
                "## Aprovação do usuário",
                "",
                "Coletada no terminal e autoritativa:",
                "",
                answers,
                "",
            ]
        )

    sections.extend(
        [
            "Execute os passos 3–5 de `quick-mode.md`:",
            "",
            "1. Atualize `.pulse/specs/quick/NNN-slug/TASK.md` → **Status: In Progress**.",
            "2. Implemente seguindo `coding-principles.md`: código mais simples que funciona,",
            "   toque **somente** os arquivos listados no TASK.md, sem scope creep.",
            "3. Verifique conforme a seção Verification do TASK.md. Só marque concluído após passar.",
            "4. Atualize `TASK.md` → **Status: Done** e marque as caixas de verificação.",
            "5. Crie `.pulse/specs/quick/NNN-slug/SUMMARY.md` com o que mudou e o resultado da verificação.",
            "6. Atualize `.pulse/specs/project/STATE.md` → linha de Quick Tasks para ✅ Done.",
            "",
            "Se o escopo crescer (>3 arquivos, decisão de design, nova dependência), **pare** e",
            "documente no TASK.md em vez de forçar a implementação.",
            "Não execute operações de git (sem commit, sem sugerir mensagens de commit).",
            "Responda em português.",
            "",
        ]
    )

    return "\n".join(sections)


def build_quick_continuation_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    plan_summary: str,
    questionnaire_answers: str,
    outcome: str,
) -> str:
    summary = format_plan_summary(plan_summary)
    sections = [
        "Continue o Quick Mode com base na escolha do usuário no terminal.",
        f"Workspace: `{workspace}`",
        f"Tarefa original: {user_prompt.strip() or 'Tarefa rápida'}",
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
        workflow="Quick mode",
        references=QUICK_PLAN_REFERENCES,
        agent_id="quick-plan",
        workspace=workspace,
    )

    if outcome == "migrate":
        sections.extend(
            [
                "O usuário escolheu **migrar para o pipeline completo**.",
                "Inicie em `specify.md` → `.pulse/specs/features/[feature]/spec.md` conforme SKILL.md.",
                "Não crie `.pulse/specs/quick/` para este pedido.",
                "Responda em português.",
                "",
            ]
        )
    elif outcome == "reduce_scope":
        sections.extend(
            [
                "O usuário escolheu um **quick fix com escopo reduzido** (opção pré-definida acima).",
                "Use essa opção como novo escopo da tarefa.",
                "Reavalie elegibilidade do Quick Mode com esse escopo específico.",
                "Se passar: crie `.pulse/specs/quick/NNN-slug/TASK.md` (Awaiting Approval), atualize STATE.md,",
                "apresente o resumo e termine com o bloco de aprovação CLI.",
                "Se ainda exceder: explique por quê e apresente novo bloco de migração com opções",
                "pré-definidas (sem \"descreva\" livre, sem \"Outro\").",
                "Não implemente código de aplicação sem aprovação.",
                "Responda em português.",
                "",
            ]
        )
    elif outcome == "adjust":
        sections.extend(
            [
                "O usuário pediu **ajustes** ao plano antes de implementar.",
                "Atualize o TASK.md e reapresente o resumo com novo bloco de aprovação.",
                "Não implemente até nova aprovação.",
                "Responda em português.",
                "",
            ]
        )
    else:
        sections.extend(
            [
                "Prossiga conforme a escolha do usuário e as regras de `quick-mode.md`.",
                "Responda em português.",
                "",
            ]
        )

    return "\n".join(sections)
