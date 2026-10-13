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


def test_a_step_configured_for_codex_carries_that_runtime(tmp_path: Path, monkeypatch):
    """The implement step's runtime is what the session must launch, not the run default."""
    from pulse.config.global_config import mark_onboarding_complete
    from pulse.config.project_settings import set_agent_field
    from pulse.runtimes import get_runtime
    from pulse.runtimes.codex import CodexRuntime

    monkeypatch.setattr(CodexRuntime, "is_available", lambda self: True)
    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="Auto",
        permission_policy="ask",
        acp_test_passed=True,
    )
    set_agent_field(tmp_path, "implement", "runtime", "codex")
    set_agent_field(tmp_path, "implement", "model", "6 Luna (medium)")

    profile = ConfiguredAgentProfiles(tmp_path, fallback_model="Auto").profile("implement")

    codex = get_runtime("codex")
    assert profile.runtime_id == "codex"
    assert profile.model == "6 Luna (medium)"
    assert list(profile.acp_command) == codex.acp_command
    assert profile.dialect is codex


def test_an_agent_missing_from_the_database_runs_without_instructions(tmp_path: Path):
    """The engine inlines instructions into the prompt; none is an empty string, not an error."""
    profile = ConfiguredAgentProfiles(tmp_path, fallback_model="auto").profile("ghost")

    assert profile.instructions == ""
    assert profile.permission_policy == "ask"
