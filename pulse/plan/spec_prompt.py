"""Prompt da classificação: decide entre o flow quick e o completo.

O texto está em `pulse/agents/bundled/classify/PHASE.md`. O que fica aqui é o
contrato: onde o agente grava a rota e como o Pulse a encontra depois
([pulse.plan.spec_route]).
"""

from __future__ import annotations

from pathlib import Path

from pulse.prompts.templates import render_shared, render_template
from pulse.skills.loader import resolve_bundled_skill
from pulse.skills.prompt import extend_prompt_with_bundled_skill

PULSE_SPEC_SKILL = "pulse-spec-driven"
ROUTE_RELATIVE_PATH = ".pulse/specs/.route.yaml"
CLASSIFY_REFERENCES = (
    "quick-mode.md",
    "prd.md",
    "user-input.md",
)


def resolve_spec_skill() -> Path:
    return resolve_bundled_skill(PULSE_SPEC_SKILL)


def route_file(workspace: Path) -> Path:
    return workspace / ROUTE_RELATIVE_PATH


def build_classify_prompt(*, workspace: Path, user_prompt: str, skill_dir: Path) -> str:
    agent_sections: list[str] = []
    extend_prompt_with_bundled_skill(
        agent_sections,
        skill_dir=skill_dir,
        skill_name=PULSE_SPEC_SKILL,
        workflow="Classify spec",
        references=CLASSIFY_REFERENCES,
        agent_id="classify",
        workspace=workspace,
    )
    return render_template(
        "classify",
        {
            "workspace": str(workspace),
            "user_prompt": user_prompt.strip() or "Untitled spec",
            "route_path": route_file(workspace).as_posix(),
            "isolation": render_shared("isolation-short", {"workspace": str(workspace)}),
            "agent": "\n".join(agent_sections).rstrip(),
        },
    )
