"""Prompts do Setup project: entrevista (fase 1) e artefatos (fase 2).

O texto está em `setup-interview/PHASE.md` e `setup-artifacts/PHASE.md`. Fica
aqui o que o Pulse precisa para orquestrar: o marcador `SETUP_READY` que separa
as duas fases e o corte do resumo que atravessa de uma para a outra.
"""

from __future__ import annotations

import re
from pathlib import Path

from pulse.prompts.templates import render_shared, render_template
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
SETUP_PROJECT_REFERENCES = ("project-init.md", "roadmap.md", "state-management.md", "user-input.md")
_ANALYSIS_MAX_CHARS = 12_000
_SETUP_READY = re.compile(r"SETUP_READY\s*", re.IGNORECASE)


def resolve_tlc_spec_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def format_analysis_summary(text: str) -> str:
    cleaned = _SETUP_READY.sub("", text).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _ANALYSIS_MAX_CHARS:
        return cleaned
    return cleaned[:_ANALYSIS_MAX_CHARS].rstrip() + "\n\n[… análise truncada …]"


def _agent_block(*, skill_dir: Path, agent_id: str, workspace: Path) -> str:
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Setup project",
        references=SETUP_PROJECT_REFERENCES,
        agent_id=agent_id,
        workspace=workspace,
    )
    return "\n".join(sections).rstrip()


def build_setup_project_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
) -> str:
    return render_template(
        "setup-interview",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "New project",
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-short", {"workspace": str(workspace)}),
            "agent": _agent_block(skill_dir=skill_dir, agent_id="setup-interview", workspace=workspace),
        },
    )


def build_setup_project_artifact_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    analysis_summary: str = "",
    questionnaire_answers: str = "",
) -> str:
    answers = questionnaire_answers.strip()
    return render_template(
        "setup-artifacts",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "New project",
            "summary": format_analysis_summary(analysis_summary)
            or "(Re-analyse the workspace — no summary captured from phase 1.)",
            "answers": answers,
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-reuse", {"workspace": str(workspace)}),
            "agent": _agent_block(skill_dir=skill_dir, agent_id="setup-artifacts", workspace=workspace),
        },
    )
