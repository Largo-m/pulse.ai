from unittest.mock import patch

from pathlib import Path

from rich.console import Console

from pulse.plan.spec_types import SPEC_TYPES
from pulse.terminal.menu import (
    build_welcome_options,
    parse_workflow_action,
    prompt_welcome_action,
    run_workflow,
)
from pulse.terminal.settings_menu import run_settings_menu
from pulse.terminal.welcome import is_pulse_ready, render_welcome


def test_render_welcome_plain():
    console = Console(force_terminal=False, width=100, record=True)
    render_welcome(console=console)
    output = console.export_text()
    assert "____" in output
    assert "Primeiro uso" in output or "Pulse configurado" in output


def test_render_welcome_ready(tmp_path: Path):
    from pulse.config.global_config import mark_onboarding_complete

    config_path = tmp_path / "config.toml"
    mark_onboarding_complete(
        agent_binary="agent",
        acp_command=["agent", "acp"],
        auth_method="cursor_login",
        workspace_dir=tmp_path,
        model="composer-2.5",
        permission_policy="ask",
        acp_test_passed=True,
        path=config_path,
    )

    console = Console(force_terminal=False, width=100, record=True)
    with console.capture():
        pass

    from pulse.config import global_config as gc

    original = gc.GLOBAL_CONFIG_FILE
    gc.GLOBAL_CONFIG_FILE = config_path
    try:
        render_welcome(cwd=tmp_path, console=console)
        output = console.export_text()
        assert "Pulse configurado" in output
        assert is_pulse_ready(tmp_path)
    finally:
        gc.GLOBAL_CONFIG_FILE = original


def test_build_welcome_options_uninitialized():
    options = build_welcome_options(False)
    labels = [option.label for option in options]
    assert "Configurar Pulse" in labels
    assert "Configurações" in labels
    assert options[0].action == "init"


def test_build_welcome_options_ready():
    options = build_welcome_options(True)
    labels = [option.label for option in options]
    assert "New issue" in labels[0]
    assert "Fix / bug" in labels[1]
    assert "Setup project" in labels[2]
    assert "Analyze codebase" in labels[3]
    assert "Configurações" in labels
    assert all(not option.action.startswith("plan") for option in options)
    assert options[0].action == "workflow:new-issue"


def test_parse_workflow_action():
    assert parse_workflow_action("workflow:new-issue") == "new-issue"
    assert parse_workflow_action("settings") is None


def test_prompt_welcome_action_non_tty(monkeypatch):
    monkeypatch.setattr("pulse.terminal.menu.is_interactive", lambda: False)
    assert prompt_welcome_action(initialized=False) is None


def test_run_workflow_includes_prompt(monkeypatch):
    monkeypatch.setattr(
        "pulse.terminal.menu.questionary.text",
        lambda *args, **kwargs: type("Answer", (), {"ask": lambda self: "Meu workflow"})(),
    )
    monkeypatch.setattr(
        "pulse.terminal.menu.run_plan",
        lambda **kwargs: 0 if kwargs["user_prompt"] == "Meu workflow" else 1,
    )
    assert run_workflow("new-issue") == 0


def test_run_workflow_setup_project_skips_prompt(monkeypatch):
    captured: dict[str, str] = {}

    def fake_run_plan(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.terminal.menu.run_plan", fake_run_plan)
    assert run_workflow("setup-project") == 0
    assert captured == {"spec_type_id": "setup-project", "user_prompt": "Novo projeto"}


def test_run_settings_menu_doctor(monkeypatch, tmp_path: Path):
    choices = iter(["doctor", "back"])

    def fake_select(*args, **kwargs):
        return type("Answer", (), {"ask": lambda self: next(choices)})()

    monkeypatch.setattr("pulse.terminal.settings_menu.questionary.select", fake_select)
    monkeypatch.setattr("pulse.terminal.settings_menu.run_doctor", lambda **kwargs: 0)
    assert run_settings_menu(cwd=tmp_path) == 0
