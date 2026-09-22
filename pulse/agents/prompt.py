from __future__ import annotations

from pulse.agents.loader import LoadedAgent


def extend_prompt_with_agent(sections: list[str], agent: LoadedAgent) -> None:
    sections.extend(
        [
            f"## Agent `{agent.definition.id}`",
            "",
            f"Você é o agent **{agent.definition.label}**.",
            agent.definition.description,
            "",
        ]
    )
    if agent.body.strip():
        sections.extend(
            [
                "Siga o playbook abaixo. Não procure SKILL.md no projeto.",
                "",
                agent.body.strip(),
                "",
            ]
        )
