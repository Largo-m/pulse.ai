"""Parsing of the `agents` and `workflows` config mappings.

Config comes from user-edited storage, so the parsers must keep every well-formed
entry and drop malformed ones instead of crashing the whole config load.
"""

from __future__ import annotations

import pytest

from pulse.config.agents import (
    AgentConfig,
    WorkflowConfig,
    default_acp_command,
    default_global_agents,
    default_global_workflows,
    parse_agents,
    parse_workflows,
)
from pulse.runtimes import RUNTIMES


@pytest.mark.parametrize("raw", [None, [], "agents", 3])
def test_agents_that_are_not_a_mapping_parse_to_none(raw: object):
    assert parse_agents(raw) == {}


def test_an_explicit_acp_command_is_kept_as_strings():
    """A user-provided command wins over the runtime default, stringified for argv."""
    agents = parse_agents({"mine": {"binary": "tool", "acp_command": ["tool", "serve", 8]}})

    assert agents == {
        "mine": AgentConfig(name="mine", binary="tool", acp_command=["tool", "serve", "8"])
    }


def test_an_agent_without_a_binary_uses_its_name_as_binary():
    agents = parse_agents({"tool": {}})

    assert agents["tool"].binary == "tool"
    assert agents["tool"].acp_command == ["tool", "acp"]


def test_an_empty_acp_command_falls_back_to_the_default():
    """An empty argv cannot be spawned; the default command is the only usable one."""
    agents = parse_agents({"tool": {"binary": "tb", "acp_command": []}})

    assert agents["tool"].acp_command == ["tb", "acp"]


def test_a_known_runtime_name_gets_the_runtime_acp_command():
    claude = RUNTIMES["claude"]

    agents = parse_agents({"claude": {}})

    assert agents["claude"].acp_command == list(claude.acp_command)
    assert agents["claude"].binary == claude.binary


def test_an_agent_named_after_a_runtime_binary_gets_that_runtime_command():
    """`find_runtime(binary)` is the second lookup: an alias pointing at a runtime id works."""
    cursor = RUNTIMES["cursor"]

    agents = parse_agents({"my-cursor": {"binary": "cursor"}})

    assert agents["my-cursor"].acp_command == list(cursor.acp_command)


def test_models_are_kept_as_strings_and_a_non_list_is_ignored():
    agents = parse_agents({"a": {"models": ["x", 2]}, "b": {"models": "x"}})

    assert agents["a"].models == ["x", "2"]
    assert agents["b"].models == []


def test_a_malformed_agent_entry_is_dropped_and_the_rest_kept():
    agents = parse_agents({"broken": "claude", "ok": {"binary": "okb"}})

    assert list(agents) == ["ok"]


def test_default_acp_command_for_an_unknown_binary_is_binary_acp():
    assert default_acp_command("nobody", "nobin") == ["nobin", "acp"]


@pytest.mark.parametrize("raw", [None, ["wf"], "wf"])
def test_workflows_that_are_not_a_mapping_parse_to_none(raw: object):
    assert parse_workflows(raw) == {}


def test_workflow_overrides_keep_agent_and_model():
    assert parse_workflows({"wf": {"agent": "claude", "model": "opus"}}) == {
        "wf": WorkflowConfig(agent="claude", model="opus")
    }


def test_empty_workflow_overrides_mean_no_override():
    """An empty string would otherwise select an agent named "", which does not exist."""
    assert parse_workflows({"wf": {"agent": "", "model": None}}) == {
        "wf": WorkflowConfig(agent=None, model=None)
    }


def test_a_malformed_workflow_entry_is_dropped():
    assert parse_workflows({"bad": "claude", "good": {}}) == {"good": WorkflowConfig()}


def test_default_global_agents_has_one_entry_per_registered_runtime():
    agents = default_global_agents()

    assert set(agents) == set(RUNTIMES)
    for runtime_id, runtime in RUNTIMES.items():
        assert agents[runtime_id] == AgentConfig(
            name=runtime_id,
            binary=runtime.binary,
            acp_command=list(runtime.acp_command),
            models=list(runtime.default_models),
        )


def test_no_workflow_is_seeded_by_default():
    """A workflow exists only in the database; config must not claim to know one."""
    assert default_global_workflows() == {}
