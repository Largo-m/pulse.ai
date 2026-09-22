from __future__ import annotations

from pathlib import Path

from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
ROUTE_RELATIVE_PATH = ".pulse/specs/.route.yaml"
CLASSIFY_REFERENCES = (
    "quick-mode.md",
    "specify.md",
    "user-input.md",
)


def resolve_spec_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def route_file(workspace: Path) -> Path:
    return workspace / ROUTE_RELATIVE_PATH


def build_classify_prompt(*, workspace: Path, user_prompt: str, skill_dir: Path) -> str:
    route_path = route_file(workspace)
    sections = [
        f"Workspace: `{workspace}`",
        f"Spec do usuário: {user_prompt.strip() or 'Spec sem título'}",
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
        workflow="Classify spec",
        references=CLASSIFY_REFERENCES,
        agent_id="classify",
        workspace=workspace,
    )
    sections.extend(
        [
            "## Fase Classificar — escolher o flow (SEM implementar)",
            "",
            "Você está conectado ao cliente **Pulse**.",
            "Classifique o pedido do usuário em **um** flow:",
            "",
            "- `quick` — Small: uma frase, ≤3 arquivos, bug/config/ajuste, sem decisão de design, sem dependência nova",
            "- `full` — Medium/Large/Complex: feature, várias histórias, design, ambiguidade, ou qualquer disqualifier de Quick mode",
            "",
            "Use a tabela de auto-sizing da skill e o **Scope Eligibility** de `quick-mode.md`.",
            "Pesquise o codebase o mínimo necessário para estimar arquivos e escopo.",
            "",
            "**Não** implemente código de aplicação.",
            "**Não** crie `spec.md`, `TASK.md`, `design.md` nem `tasks.md`.",
            "**Não** pergunte ao usuário. Decida.",
            "",
            f"Grave exatamente este arquivo: `{route_path}`",
            "",
            "Conteúdo YAML (sem fence, sem texto extra no arquivo):",
            "",
            "```yaml",
            "flow: quick",
            "reason: Uma frase objetiva com o motivo",
            "```",
            "",
            "`flow` deve ser `quick` ou `full`.",
            "Depois de gravar o arquivo, pare.",
            "",
        ]
    )
    return "\n".join(sections)
