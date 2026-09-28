"""Prompts do Analyze codebase: exploração (fase 1) e documentação (fase 2).

O texto está em `codebase-explore/PHASE.md` e `codebase-docs/PHASE.md`. Fica
aqui o marcador `ANALYZE_READY` que fecha a fase 1 e a lista de artefatos que a
fase 2 precisa produzir.
"""

from __future__ import annotations

import re
from pathlib import Path

from pulse.prompts.templates import render_shared, render_template
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


def _agent_block(*, skill_dir: Path, agent_id: str, workspace: Path) -> str:
    sections: list[str] = []
    extend_prompt_with_bundled_skill(
        sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Analyze codebase",
        references=ANALYZE_CODEBASE_REFERENCES,
        agent_id=agent_id,
        workspace=workspace,
    )
    return "\n".join(sections).rstrip()


def build_analyze_codebase_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
) -> str:
    return render_template(
        "codebase-explore",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Map the existing codebase",
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-short", {"workspace": str(workspace)}),
            "agent": _agent_block(skill_dir=skill_dir, agent_id="codebase-explore", workspace=workspace),
        },
    )


def build_analyze_codebase_artifact_prompt(
    *,
    workspace: Path,
    user_prompt: str,
    skill_dir: Path,
    analysis_summary: str = "",
    questionnaire_answers: str = "",
) -> str:
    return render_template(
        "codebase-docs",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Map the existing codebase",
            "summary": format_analysis_summary(analysis_summary)
            or "(Re-explore the workspace — no summary captured from phase 1.)",
            "answers": questionnaire_answers.strip(),
            "artifact_list": "\n".join(
                f"- `.pulse/specs/codebase/{name}`" for name in CODEBASE_ARTIFACTS
            ),
            "output_language": render_shared("output-language"),
            "isolation": render_shared("isolation-reuse", {"workspace": str(workspace)}),
            "agent": _agent_block(skill_dir=skill_dir, agent_id="codebase-docs", workspace=workspace),
        },
    )
