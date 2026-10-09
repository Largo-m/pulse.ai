"""`ConfiguredAgentProfiles`: what a step's agent runs with, read from config and the database."""

from __future__ import annotations

from pathlib import Path

from pulse.config.agent_profiles import ConfiguredAgentProfiles
from pulse.domain.ports import AgentProfiles
from pulse.domain.workflow import AgentDef
from pulse.store.workflow_defs import save_agent


def test_the_adapter_implements_the_port(tmp_path: Path):
    assert isinstance(ConfiguredAgentProfiles(tmp_path, fallback_model=None), AgentProfiles)


def test_the_agent_definition_sets_model_policy_and_instructions(tmp_path: Path):
    save_agent(
        AgentDef(
            id="reviewer",
            label="Reviewer",
            model="opus",
            permission_policy="deny_writes",
            instructions="  Revise sem editar.\n",
        )
    )

    profile = ConfiguredAgentProfiles(tmp_path, fallback_model="auto").profile("reviewer")

    assert (profile.agent_id, profile.model, profile.permission_policy) == (
        "reviewer",
        "opus",
        "deny_writes",
    )
    assert profile.instructions == "Revise sem editar."


def test_an_agent_missing_from_the_database_runs_without_instructions(tmp_path: Path):
    """The engine inlines instructions into the prompt; none is an empty string, not an error."""
    profile = ConfiguredAgentProfiles(tmp_path, fallback_model="auto").profile("ghost")

    assert profile.instructions == ""
    assert profile.permission_policy == "ask"
