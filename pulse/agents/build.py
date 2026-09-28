"""Monta os AGENT.md a partir das references do skill.

Cada agente bundled é o frontmatter do catálogo seguido das references que ele
declara em `source_files`, concatenadas na ordem. O conteúdo vive uma vez só em
`pulse/skills/pulse-spec-driven/references/`; aqui ele é copiado para dentro do
bundle porque o agente recebe o playbook inline no prompt e não lê o skill do
disco.

Editar um AGENT.md à mão faz o bundle divergir da reference sem ninguém notar —
`test_agents_bundle_is_in_sync` quebra quando isso acontece. Depois de mexer em
uma reference, rode:

    python -m pulse.agents.build
"""

from __future__ import annotations

from pathlib import Path

from pulse.agents.catalog import BUNDLED_AGENTS, AgentDefinition
from pulse.skills.loader import resolve_bundled_skill

SKILL_NAME = "pulse-spec-driven"


def bundled_agents_dir() -> Path:
    return Path(__file__).resolve().parent / "bundled"


def references_dir() -> Path:
    return resolve_bundled_skill(SKILL_NAME) / "references"


def _frontmatter(agent: AgentDefinition) -> str:
    return "\n".join(
        [
            "---",
            f"name: {agent.id}",
            f"description: {agent.description}",
            f"runtime: {agent.runtime}",
            f"model: {agent.model}",
            f"permission_policy: {agent.permission_policy}",
            "---",
            "",
        ]
    )


def render_agent(agent: AgentDefinition, *, references: Path | None = None) -> str:
    root = references or references_dir()
    parts = [_frontmatter(agent)]
    for name in agent.source_files:
        source = root / name
        if not source.is_file():
            raise FileNotFoundError(f"reference ausente para `{agent.id}`: {source}")
        # O título repete o nome do arquivo para o agente saber de onde veio o
        # trecho quando o playbook cita `[outra.md](outra.md)`.
        parts.append(f"\n# {name}\n\n{source.read_text(encoding='utf-8').strip()}\n")
    return "".join(parts)


def build_all(*, write: bool = True) -> list[str]:
    """Regrava os AGENT.md. Devolve os ids que estavam fora de sincronia."""
    stale: list[str] = []
    for agent in BUNDLED_AGENTS:
        if not agent.source_files:
            continue
        target = bundled_agents_dir() / agent.id / "AGENT.md"
        rendered = render_agent(agent)
        current = target.read_text(encoding="utf-8") if target.is_file() else ""
        if current == rendered:
            continue
        stale.append(agent.id)
        if write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(rendered, encoding="utf-8")
    return stale


def main() -> int:
    stale = build_all()
    if not stale:
        print("[pulse] agents já estavam em sincronia")
        return 0
    for agent_id in stale:
        print(f"[pulse] regerado: {agent_id}/AGENT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
