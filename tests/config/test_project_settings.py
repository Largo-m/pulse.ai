"""Which value the settings screen shows: the agent's own, the project's, the machine's.

This used to be computed inside the screen; the daemon now decides it, so the
order of precedence is pinned here.
"""

from __future__ import annotations

from pathlib import Path

from pulse.config.global_config import mark_onboarding_complete
from pulse.config.project_config import init_project_config, load_project_config
from pulse.config.project_settings import (
    FALLBACK_MODEL,
    FALLBACK_POLICY,
    FALLBACK_RUNTIME,
    AgentFields,
    agent_fields,
    effective_defaults,
    project_settings,
    set_agent_field,
    set_project_default,
)
from pulse.store.workflow_defs import list_agents


def _machine(workspace: Path, *, model: str = "machine-model") -> None:
    mark_onboarding_complete(
        agent_binary="claude",
        acp_command=["claude-acp"],
        auth_method="login",
        workspace_dir=workspace,
        model=model,
        permission_policy="deny_writes",
        acp_test_passed=True,
        default_agent="claude",
    )


def test_without_any_choice_the_defaults_are_pulse_s_own(tmp_path: Path) -> None:
    assert effective_defaults(tmp_path) == AgentFields(
        FALLBACK_RUNTIME, FALLBACK_MODEL, FALLBACK_POLICY
    )


def test_the_project_overrides_the_machine_field_by_field(tmp_path: Path) -> None:
    _machine(tmp_path)
    init_project_config(tmp_path)

    set_project_default(tmp_path, "model", "project-model")

    assert effective_defaults(tmp_path) == AgentFields("claude", "project-model", "deny_writes")


def test_an_agent_s_own_setting_wins_over_the_project_default(tmp_path: Path) -> None:
    init_project_config(tmp_path)
    first, second = list_agents()[:2]
    set_project_default(tmp_path, "model", "everyone")

    set_agent_field(tmp_path, first.id, "model", "only-me")

    assert agent_fields(tmp_path, first.id) == AgentFields(
        FALLBACK_RUNTIME, "only-me", FALLBACK_POLICY
    )
    second_fields = agent_fields(tmp_path, second.id)
    assert second_fields is not None
    assert second_fields.model == "everyone"


def test_a_later_project_default_overwrites_every_agent(tmp_path: Path) -> None:
    """A point-in-time write, not a layer: setting the default again resets the agents."""
    init_project_config(tmp_path)
    first = list_agents()[0]
    set_agent_field(tmp_path, first.id, "model", "only-me")

    set_project_default(tmp_path, "model", "everyone")

    fields = agent_fields(tmp_path, first.id)
    assert fields is not None
    assert fields.model == "everyone"


def test_an_unknown_agent_has_no_fields(tmp_path: Path) -> None:
    assert agent_fields(tmp_path, "nope") is None


def test_the_settings_list_every_agent_and_the_worktree_switch(tmp_path: Path) -> None:
    init_project_config(tmp_path)

    settings = project_settings(tmp_path)

    assert [agent.id for agent in settings.agents] == [agent.id for agent in list_agents()]
    project = load_project_config(tmp_path)
    assert project is not None
    assert settings.use_worktree is project.use_worktree is False
