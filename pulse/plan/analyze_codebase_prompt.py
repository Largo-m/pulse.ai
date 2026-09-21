from __future__ import annotations

import re
from pathlib import Path

from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
ANALYZE_CODEBASE_REFERENCES = (
    "brownfield-mapping.md",
    "concerns.md",
    "code-analysis.md",
    "user-input.md",
)
_ANALYSIS_MAX_CHARS = 16_000
_ANALYZE_READY = re.compile(r"ANALYZE_READY\s*", re.IGNORECASE)

CODEBASE_ARTIFACTS = (
    "STACK.md",
    "ARCHITECTURE.md",
    "CONVENTIONS.md",
    "STRUCTURE.md",
    "TESTING.md",
    "INTEGRATIONS.md",
    "CONCERNS.md",
)


def resolve_analyze_codebase_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def format_analysis_summary(text: str) -> str:
    cleaned = _ANALYZE_READY.sub("", text).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _ANALYSIS_MAX_CHARS:
        return cleaned
    return cleaned[:_ANALYSIS_MAX_CHARS].rstrip() + "\n\n[… análise truncada …]"


def build_analyze_codebase_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
) -> str:
    sections = [
        f"Workspace: `{workspace}`",
        f"Contexto do usuário: {user_prompt.strip() or 'Mapear codebase existente'}",
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
        workflow="Analyze codebase",
        references=ANALYZE_CODEBASE_REFERENCES,
    )
    sections.extend(
        [
            "## Fase 1 — Exploração do codebase",
            "",
            "Você está conectado ao cliente **Pulse**.",
            "Explore o repositório sistematicamente **antes** de encerrar esta fase.",
            "",
            "### O que explorar",
            "",
            "Siga `brownfield-mapping.md`:",
            "- Estrutura de diretórios e organização de módulos",
            "- Stack a partir de manifests de dependência e configuração de build",
            "- Padrões arquiteturais em amostras representativas (5–10 arquivos por categoria)",
            "- Convenções de código observadas no código real",
            "- Infraestrutura de testes e comandos de execução",
            "- Integrações externas (APIs, serviços, webhooks, jobs)",
            "- Sinais de preocupação: dívida técnica, gaps de teste, riscos de segurança",
            "",
            "Use as ferramentas de análise descritas em `code-analysis.md`.",
            "Se o skill `codenavi` estiver disponível no ambiente, prefira-o para navegação.",
            "",
            "### Perguntas — somente se indispensável",
            "",
            "Este fluxo é **autônomo**. Só pergunte se for impossível prosseguir sem uma decisão do",
            "usuário (ex.: monorepo com múltiplos produtos, escopo ambíguo).",
            "",
            "Você **não** tem ferramentas externas para perguntar. Se precisar, escreva as perguntas",
            "em um **bloco de texto** que o Pulse renderiza no terminal, no formato:",
            "```text",
            "Preciso de algumas informações antes de continuar.",
            "1. Pergunta?",
            "A) Opção A",
            "B) Opção B",
            "```",
            "Faça todas as perguntas necessárias em um único bloco e não escreva texto fora dele.",
            "",
            "PROIBIDO nesta fase:",
            "- Criar ou editar arquivos.",
            "- Se for perguntar, enviar qualquer texto fora do bloco ```text.",
            "- Inventar stack, padrões ou integrações sem evidência no código.",
            "",
            "Ao concluir a exploração, responda **somente** a palavra `ANALYZE_READY` — "
            "sem frases antes ou depois. O Pulse usa isso internamente e não exibe no terminal.",
            "",
        ]
    )

    return "\n".join(sections)


def build_analyze_codebase_artifact_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    analysis_summary: str = "",
    questionnaire_answers: str = "",
) -> str:
    summary = format_analysis_summary(analysis_summary)
    answers = questionnaire_answers.strip()
    artifact_list = "\n".join(f"- `.pulse/specs/codebase/{name}`" for name in CODEBASE_ARTIFACTS)
    sections = [
        "Fase 2 do Analyze codebase — criar documentação brownfield em `.pulse/specs/codebase/`.",
        f"Workspace: `{workspace}`",
        f"Contexto inicial: {user_prompt.strip() or 'Mapear codebase existente'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        f"Use **somente** o workspace `{workspace}` e a análise desta execução abaixo.",
        "Não reutilize conversas anteriores, outros repositórios ou execuções passadas do Pulse.",
        "",
    ]
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Analyze codebase",
        references=ANALYZE_CODEBASE_REFERENCES,
    )
    sections.extend(
        [
            "## Análise desta execução (fase 1)",
            "",
            summary or "(Reexplore o workspace — nenhum resumo capturado da fase 1.)",
            "",
        ]
    )

    if answers:
        sections.extend(
            [
                "## Respostas do usuário (questionário)",
                "",
                "Estas respostas foram coletadas no terminal e são autoritativas:",
                "",
                answers,
                "",
            ]
        )

    sections.extend(
        [
            "Crie os 7 artefatos conforme `brownfield-mapping.md`:",
            artifact_list,
            "",
            "Para `CONCERNS.md`, siga o template em `concerns.md`.",
            "Documente apenas o que tiver evidência concreta (caminhos, padrões, comandos).",
            "Respeite os limites de tamanho de cada arquivo descritos em `brownfield-mapping.md`.",
            "Responda em português.",
            "",
        ]
    )

    return "\n".join(sections)
