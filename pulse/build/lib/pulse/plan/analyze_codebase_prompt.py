from __future__ import annotations

import re
from pathlib import Path

from pulse.skills.loader import load_bundled_skill

TLC_SPEC_SKILL = "tlc-spec-driven"
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


def resolve_analyze_codebase_skill() -> tuple[Path, dict[str, str]]:
    return load_bundled_skill(TLC_SPEC_SKILL, references=ANALYZE_CODEBASE_REFERENCES)


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
    documents: dict[str, str],
) -> str:
    sections = [
        "Execute o fluxo **Analyze codebase** (brownfield mapping) do skill `tlc-spec-driven`.",
        f"Workspace: `{workspace}`",
        f"Contexto do usuário: {user_prompt.strip() or 'Mapear codebase existente'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        "Esta é uma execução **nova e isolada** do Pulse.",
        f"Analise **somente** o workspace `{workspace}`.",
        "Ignore conversas anteriores do Cursor, outros projetos e execuções passadas do Pulse.",
        "",
        "## Fase 1 — Exploração do codebase (ACP)",
        "",
        "Você está conectado ao cliente **Pulse** via ACP.",
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
        "Este fluxo é **autônomo**. Só invoque `cursor/ask_question` se for impossível",
        "prosseguir sem uma decisão do usuário (ex.: monorepo com múltiplos produtos,",
        "escopo ambíguo). Documentação: https://cursor.com/docs/cli/acp#cursorask_question",
        "",
        "Regras do questionário ACP (quando necessário):",
        "- **Uma pergunta por chamada** — envie exatamente um item em `questions`.",
        "- Na **primeira** pergunta de um lote, inclua `title`:",
        '  `"Preciso de algumas informações antes de continuar."`',
        "- Informe progresso com `questionIndex` e `totalQuestions`.",
        "",
        "PROIBIDO nesta fase:",
        "- Criar ou editar arquivos.",
        "- Escrever perguntas no texto do chat (use `cursor/ask_question`).",
        "- Inventar stack, padrões ou integrações sem evidência no código.",
        "",
        "Ao concluir a exploração, responda **somente** a palavra `ANALYZE_READY` — "
        "sem frases antes ou depois. O Pulse usa isso internamente e não exibe no terminal.",
        "",
    ]

    for name, content in documents.items():
        if name in {"user-input.md", "SKILL.md"}:
            continue
        sections.extend(
            [
                "---",
                f"## {name}",
                content.strip(),
                "",
            ]
        )

    return "\n".join(sections)


def build_analyze_codebase_artifact_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    documents: dict[str, str],
    analysis_summary: str = "",
) -> str:
    summary = format_analysis_summary(analysis_summary)
    artifact_list = "\n".join(f"- `.specs/codebase/{name}`" for name in CODEBASE_ARTIFACTS)
    sections = [
        "Fase 2 do Analyze codebase — criar documentação brownfield em `.specs/codebase/`.",
        f"Workspace: `{workspace}`",
        f"Contexto inicial: {user_prompt.strip() or 'Mapear codebase existente'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        f"Use **somente** o workspace `{workspace}` e a análise desta execução abaixo.",
        "Não reutilize conversas anteriores, outros repositórios ou execuções passadas do Pulse.",
        "",
        "## Análise desta execução (fase 1)",
        "",
        summary or "(Reexplore o workspace — nenhum resumo capturado da fase 1.)",
        "",
        "Se ainda faltar informação crítica, invoque `cursor/ask_question` (uma pergunta por vez).",
        "",
        "Crie os 7 artefatos conforme `brownfield-mapping.md`:",
        artifact_list,
        "",
        "Para `CONCERNS.md`, siga o template em `concerns.md`.",
        "Documente apenas o que tiver evidência concreta (caminhos, padrões, comandos).",
        "Respeite os limites de tamanho de cada arquivo descritos em `brownfield-mapping.md`.",
        "Responda em português.",
        "",
    ]

    for name, content in documents.items():
        if name == "SKILL.md":
            continue
        sections.extend(
            [
                "---",
                f"## {name}",
                content.strip(),
                "",
            ]
        )

    return "\n".join(sections)
