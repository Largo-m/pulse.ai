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
        "## Fase 1 — Análise e questionário (ACP)",
        "",
        "Você está conectado ao cliente **Pulse** via ACP.",
        "Analise o workspace e os artefatos existentes **antes** de perguntar qualquer coisa.",
        "",
        "### Perguntas — somente via ACP",
        "",
        "Todas as perguntas ao usuário **devem** usar o método bloqueante **`cursor/ask_question`**.",
        "O Pulse **não** gera perguntas — apenas renderiza o que o agente enviar via ACP.",
        "Documentação: https://cursor.com/docs/cli/acp#cursorask_question",
        "",
        "Após analisar o workspace, verifique se `.specs/project/PROJECT.md` documenta **explicitamente**:",
        "visão, público-alvo, foco da v1 e restrições.",
        "",
        "Se **qualquer** campo estiver ausente ou ambíguo, invoque `cursor/ask_question`",
        "(uma pergunta por chamada) **antes** de `SETUP_READY`.",
        "Se todos estiverem claros no repositório, encerre com `SETUP_READY` sem perguntar.",
        "",
        "### Regras do questionário ACP",
        "- **Uma pergunta por chamada** — envie exatamente um item em `questions`.",
        "- **Todas respondidas antes de continuar** — se iniciar um questionário, faça todas as",
        "  chamadas necessárias na mesma sessão antes de encerrar a fase.",
        "- Na **primeira** pergunta de um lote, inclua `title`:",
        '  `"Preciso de algumas informações antes de continuar."`',
        "- Informe progresso com `questionIndex` e `totalQuestions` (ex.: 2 de 4).",
        "- Opções concretas em `options`; o Pulse adiciona **Outro** automaticamente.",
        "- Siga os tópicos de `project-init.md` (visão, público, escopo v1, restrições).",
        "",
        "Exemplo de params para a pergunta 2 de 4:",
        "```json",
        "{",
        '  "title": "Preciso de algumas informações antes de continuar.",',
        '  "questionIndex": 2,',
        '  "totalQuestions": 4,',
        '  "questions": [{',
        '    "id": "audience",',
        '    "prompt": "2. Quem é o público-alvo e qual problema resolve?",',
        '    "options": [',
        '      {"id": "beginners", "label": "Investidores iniciantes aprendendo a operar"},',
        '      {"id": "devs", "label": "Desenvolvedores estudando arquitetura"}',
        "    ]",
        "  }]",
        "}",
        "```",
        "",
        "PROIBIDO nesta fase:",
        "- Criar ou editar arquivos.",
        "- Escrever perguntas no texto do chat (use `cursor/ask_question`).",
        "- Executar shell/python para simular perguntas.",
        "- Ler `.pulse/skills/` ou arquivos de entrevista legados.",
        "- Encerrar com `SETUP_READY` se ainda faltarem campos obrigatórios não documentados.",
        "",
        "Ao concluir a análise (com ou sem perguntas), responda **somente** a palavra `SETUP_READY` — "
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
) -> str:
    summary = format_analysis_summary(analysis_summary)
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
        "Se ainda faltar informação crítica, invoque `cursor/ask_question` (uma pergunta por vez).",
        "",
        "Explore o workspace se necessário e crie:",
        "- `.specs/project/PROJECT.md` conforme `project-init.md`.",
        "- `.specs/project/ROADMAP.md` conforme `roadmap.md`.",
        "- `.specs/project/STATE.md` conforme `state-management.md`.",
        "- Responda em português.",
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
