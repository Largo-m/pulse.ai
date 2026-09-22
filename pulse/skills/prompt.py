from __future__ import annotations

from pathlib import Path

from pulse.agents.loader import load_agent
from pulse.agents.prompt import extend_prompt_with_agent


def extend_prompt_with_bundled_skill(
    sections: list[str],
    *,
    skill_dir: Path,
    skill_name: str,
    workflow: str,
    references: tuple[str, ...] = (),
    agent_id: str | None = None,
    workspace: Path | None = None,
) -> None:
    if agent_id:
        agent = load_agent(agent_id, workspace=workspace)
        if agent is not None:
            extend_prompt_with_agent(sections, agent)
            return
    skill_file = skill_dir / "SKILL.md"
    sections.extend(
        [
            "## Skill",
            "",
            f"Use a skill instalada: `{skill_name}`",
            f"Siga o workflow **{workflow}**.",
            "",
            "Leia os arquivos abaixo no filesystem antes de agir (conteúdo não está no prompt):",
            f"- `{skill_file}`",
        ]
    )
    references_dir = skill_dir / "references"
    for reference in references:
        reference_path = references_dir / reference
        if reference_path.is_file():
            sections.append(f"- `{reference_path}`")
    sections.extend(
        [
            "",
            "Leia apenas as referências necessárias para o passo atual.",
            "",
        ]
    )
