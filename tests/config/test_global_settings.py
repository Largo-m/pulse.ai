"""Global writes to every agent; a later specific change applies only to that agent."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("textual")

from pulse.config.project_config import init_project_config, load_project_config
from pulse.config.resolved import resolve_config
from pulse.store.agent_settings import (
    apply_setting_to_all_agents,
    load_agent_settings,
    upsert_agent_settings,
)
from pulse.tui.screens.settings import SettingsScreen


def _project_id(tmp_path: Path) -> str:
    init_project_config(tmp_path)
    project = load_project_config(tmp_path)
    assert project is not None
    return project.project_id


def test_global_overwrites_the_agents_that_already_had_a_value(tmp_path: Path):
    project_id = _project_id(tmp_path)
    upsert_agent_settings(project_id, "alpha", model="composer-2.5")

    apply_setting_to_all_agents(
        project_id, field="model", value="opus[1m]", agent_ids=["alpha", "beta"]
    )

    assert load_agent_settings(project_id, "alpha")["model"] == "opus[1m]"
    assert load_agent_settings(project_id, "beta")["model"] == "opus[1m]"


def test_a_specific_change_after_the_global_wins(tmp_path: Path):
    project_id = _project_id(tmp_path)
    apply_setting_to_all_agents(
        project_id, field="runtime", value="claude", agent_ids=["alpha", "beta"]
    )

    upsert_agent_settings(project_id, "alpha", runtime="cursor")

    assert load_agent_settings(project_id, "alpha")["runtime"] == "cursor"
    assert load_agent_settings(project_id, "beta")["runtime"] == "claude"


def test_global_does_not_touch_the_other_fields(tmp_path: Path):
    project_id = _project_id(tmp_path)
    upsert_agent_settings(project_id, "alpha", model="composer-2.5", runtime="cursor")

    apply_setting_to_all_agents(
        project_id, field="permission_policy", value="auto_approve", agent_ids=["alpha"]
    )

    stored = load_agent_settings(project_id, "alpha")
    assert stored["permission_policy"] == "auto_approve"
    assert stored["model"] == "composer-2.5"
    assert stored["runtime"] == "cursor"


def test_unknown_field_is_ignored(tmp_path: Path):
    project_id = _project_id(tmp_path)
    upsert_agent_settings(project_id, "alpha", model="composer-2.5")

    apply_setting_to_all_agents(
        project_id, field="binary; DROP TABLE agent_settings", value="x", agent_ids=["alpha"]
    )

    assert load_agent_settings(project_id, "alpha")["model"] == "composer-2.5"


def test_saving_global_reaches_the_agent_used_by_the_run(tmp_path: Path):
    init_project_config(tmp_path)
    screen = SettingsScreen(cwd=tmp_path)
    screen._target = "global"
    calls: list[str] = []
    screen._show_global_fields = lambda: calls.append("back")  # type: ignore[method-assign]

    screen._save_global(field="model", value="opus[1m]")

    project = load_project_config(tmp_path)
    assert project is not None
    assert project.model == "opus[1m]"
    assert resolve_config(tmp_path, pulse_agent="default").model == "opus[1m]"
    assert calls == ["back"]


def test_saving_global_permission_and_runtime_lands_on_the_project(tmp_path: Path):
    init_project_config(tmp_path)
    screen = SettingsScreen(cwd=tmp_path)
    screen._target = "global"
    screen._show_global_fields = lambda: None  # type: ignore[method-assign]

    screen._save_global(field="permission_policy", value="auto_approve")
    screen._save_global(field="runtime", value="claude")

    project = load_project_config(tmp_path)
    assert project is not None
    assert project.permission_policy == "auto_approve"
    assert project.default_agent == "claude"
    assert screen._effective_global_fields() == ("claude", "Auto", "auto_approve")
