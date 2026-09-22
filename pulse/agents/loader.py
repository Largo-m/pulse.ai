from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pulse.agents.catalog import AGENT_BY_ID, AgentDefinition, BUNDLED_AGENTS


@dataclass(frozen=True)
class LoadedAgent:
    definition: AgentDefinition
    body: str
    origin: str
    path: Path | None
    runtime: str
    model: str
    permission_policy: str


def bundled_agents_dir() -> Path:
    return Path(__file__).resolve().parent / "bundled"


def parse_agent_markdown(text: str, fallback: AgentDefinition) -> tuple[dict[str, str], str]:
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return {}, text
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, parts[2].lstrip("\n")


def _agent_paths(workspace: Path | None, agent_id: str) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = [
        ("bundled", bundled_agents_dir() / agent_id / "AGENT.md"),
    ]
    if workspace is not None:
        root = workspace.resolve()
        paths.extend(
            [
                ("project", root / ".pulse" / "agents" / agent_id / "AGENT.md"),
                ("claude", root / ".claude" / "agents" / f"{agent_id}.md"),
                ("cursor", root / ".cursor" / "agents" / f"{agent_id}.md"),
            ]
        )
    return paths


def _discover_extra_ids(workspace: Path | None) -> list[str]:
    if workspace is None:
        return []
    extras: list[str] = []
    root = workspace.resolve()
    candidates = [
        root / ".pulse" / "agents",
        root / ".claude" / "agents",
        root / ".cursor" / "agents",
    ]
    for directory in candidates:
        if not directory.is_dir():
            continue
        for item in directory.iterdir():
            if item.is_dir() and (item / "AGENT.md").is_file():
                extras.append(item.name)
            elif item.is_file() and item.suffix == ".md":
                extras.append(item.stem)
    unique: list[str] = []
    known = set(AGENT_BY_ID)
    for agent_id in extras:
        if agent_id not in known and agent_id not in unique:
            unique.append(agent_id)
    return unique


def load_agent(
    agent_id: str,
    *,
    workspace: Path | None = None,
) -> LoadedAgent | None:
    fallback = AGENT_BY_ID.get(agent_id)
    if fallback is None:
        fallback = AgentDefinition(
            id=agent_id,
            label=agent_id,
            description=agent_id,
        )
    chosen: tuple[str, Path] | None = None
    for origin, path in _agent_paths(workspace, agent_id):
        if path.is_file():
            chosen = (origin, path)
    if chosen is None:
        if agent_id not in AGENT_BY_ID:
            return None
        return LoadedAgent(
            definition=fallback,
            body="",
            origin="catalog",
            path=None,
            runtime=fallback.runtime,
            model=fallback.model,
            permission_policy=fallback.permission_policy,
        )
    origin, path = chosen
    text = path.read_text(encoding="utf-8")
    meta, body = parse_agent_markdown(text, fallback)
    return LoadedAgent(
        definition=fallback,
        body=body,
        origin=origin,
        path=path,
        runtime=meta.get("runtime", fallback.runtime),
        model=meta.get("model", fallback.model),
        permission_policy=meta.get("permission_policy", fallback.permission_policy),
    )


def load_agents(*, workspace: Path | None = None) -> list[LoadedAgent]:
    agents: list[LoadedAgent] = []
    for definition in BUNDLED_AGENTS:
        loaded = load_agent(definition.id, workspace=workspace)
        if loaded is not None:
            agents.append(loaded)
    for extra_id in _discover_extra_ids(workspace):
        loaded = load_agent(extra_id, workspace=workspace)
        if loaded is not None:
            agents.append(loaded)
    return agents
