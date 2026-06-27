from __future__ import annotations

import re
from pathlib import Path

from pulse.skills.loader import load_bundled_skill

TLC_SPEC_SKILL = "tlc-spec-driven"
SETUP_PROJECT_REFERENCES = ("project-init.md", "roadmap.md", "state-management.md", "user-input.md")
_ANALYSIS_MAX_CHARS = 12_000
_SETUP_READY = re.compile(r"SETUP_READY\s*", re.IGNORECASE)


def resolve_tlc_spec_skill() -> tuple[Path, dict[str, str]]:
    return load_bundled_skill(TLC_SPEC_SKILL, references=SETUP_PROJECT_REFERENCES)


def format_analysis_summary(text: str) -> str:
    cleaned = _SETUP_READY.sub("", text).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _ANALYSIS_MAX_CHARS:
        return cleaned
    return cleaned[:_ANALYSIS_MAX_CHARS].rstrip() + "\n\n[… análise truncada …]"


def build_setup_project_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    documents: dict[str, str],
) -> str:
    sections = [
        "Execute o fluxo **Setup project** do skill `tlc-spec-driven`.",
        f"Workspace: `{workspace}`",
        f"Contexto do usuário: {user_prompt.strip() or 'Novo projeto'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        "Esta é uma execução **nova e isolada** do Pulse.",
        f"Analise **somente** o workspace `{workspace}`.",
        "Ignore conversas anteriores do Cursor, outros projetos e execuções passadas do Pulse.",
        "",
        "## Fase 1 — Análise e questionário",
        "",
        "Você está conectado ao cliente **Pulse**.",
        "Analise o workspace e os artefatos existentes **antes** de perguntar qualquer coisa.",
        "",
        "### Perguntas — em bloco de texto estruturado",
        "",
        "Você **não** tem ferramentas externas para perguntar ao usuário. Quando precisar de",
        "informação, escreva as perguntas em um **bloco de texto** no formato exato abaixo.",
        "O Pulse detecta esse bloco, renderiza um questionário interativo no terminal e coleta",
        "as respostas para a próxima fase.",
        "",
        "Após analisar o workspace, verifique se há informação **explícita** sobre:",
        "visão, público-alvo, foco da v1 e restrições (em `.specs/project/PROJECT.md`, README ou docs).",
        "",
        "- Se **qualquer** campo estiver ausente ou ambíguo, responda **apenas** com o bloco de",
        "  perguntas (sem `SETUP_READY` e sem texto antes ou depois).",
        "- Se estiver tudo claro no repositório, responda **somente** `SETUP_READY`.",
        "",
        "### Formato obrigatório do bloco de perguntas",
        "",
        "- Abra uma cerca ```text e use como primeira linha, exatamente:",
        '  `Preciso de algumas informações antes de continuar.`',
        "- Cada pergunta numerada (`1.`, `2.`, …), uma por linha.",
        "- Cada opção com letra maiúscula (`A)`, `B)`, …); o Pulse adiciona **Outro** automaticamente.",
        "- Faça **todas** as perguntas necessárias em um **único** bloco.",
        "- Cubra os tópicos de `project-init.md` (visão, público, escopo v1, restrições).",
        "",
        "Exemplo:",
        "```text",
        "Preciso de algumas informações antes de continuar.",
        "1. Qual é a visão do produto?",
        "A) Plataforma de paper trading para estudo",
        "B) Ferramenta de análise para investidores reais",
        "2. Quem é o público-alvo?",
        "A) Investidores iniciantes",
        "B) Desenvolvedores estudando arquitetura",
        "```",
        "",
        "PROIBIDO nesta fase:",
        "- Criar ou editar arquivos.",
        "- Se for perguntar, enviar qualquer texto fora do bloco ```text.",
        "- Executar shell/python para simular perguntas.",
        "- Ler `.pulse/skills/` ou arquivos de entrevista legados.",
        "- Responder `SETUP_READY` se ainda faltarem campos obrigatórios não documentados.",
        "",
        "Quando tudo estiver claro (sem perguntas), responda **somente** a palavra `SETUP_READY` — "
        "sem frases antes ou depois. O Pulse usa isso internamente e não exibe no terminal.",
        "",
    ]

    for name, content in documents.items():
        if name in {"user-input.md", "SKILL.md", "project-init.md"}:
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


def build_setup_project_artifact_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    documents: dict[str, str],
    analysis_summary: str = "",
    questionnaire_answers: str = "",
) -> str:
    summary = format_analysis_summary(analysis_summary)
    answers = questionnaire_answers.strip()
    sections = [
        "Fase 2 do Setup project — criar artefatos em `.specs/project/`.",
        f"Workspace: `{workspace}`",
        f"Contexto inicial: {user_prompt.strip() or 'Novo projeto'}",
        "",
        "## Isolamento (obrigatório)",
        "",
        f"Use **somente** o workspace `{workspace}` e a análise desta execução abaixo.",
        "Não reutilize conversas anteriores, outros repositórios ou execuções passadas do Pulse.",
        "",
        "## Análise desta execução (fase 1)",
        "",
        summary or "(Reanalise o workspace — nenhum resumo capturado da fase 1.)",
        "",
    ]

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
            "Use as respostas acima como fonte de verdade. Não invente o que não foi respondido.",
            "",
        ]
    )

    sections.extend(
        [
            "Explore o workspace se necessário e crie:",
            "- `.specs/project/PROJECT.md` conforme `project-init.md`.",
            "- `.specs/project/ROADMAP.md` conforme `roadmap.md`.",
            "- `.specs/project/STATE.md` conforme `state-management.md`.",
            "- Responda em português.",
            "",
        ]
    )

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
