from __future__ import annotations

from pulse.agents.catalog import (
    ANALYZE_AGENTS,
    SETUP_AGENTS,
    SPEC_FULL_AGENTS,
    SPEC_QUICK_AGENTS,
    WORKFLOW_AGENTS,
)


def compose_workflow_agents(workflow_id: str) -> tuple[str, ...]:
    return WORKFLOW_AGENTS.get(workflow_id, ())


def expand_spec_flow(flow: str) -> tuple[str, ...]:
    if flow == "quick":
        return ("classify",) + SPEC_QUICK_AGENTS
    return ("classify",) + SPEC_FULL_AGENTS


def compose_setup_agents() -> tuple[str, ...]:
    return SETUP_AGENTS


def compose_analyze_agents() -> tuple[str, ...]:
    return ANALYZE_AGENTS
