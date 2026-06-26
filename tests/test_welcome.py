from unittest.mock import patch

from pathlib import Path

from rich.console import Console

from pulse.plan.spec_types import SPEC_TYPES
from pulse.terminal.menu import _resolve_plan_argv, build_welcome_options, prompt_welcome_action
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
    assert options[0].argv == ["init"]


def test_build_welcome_options_ready():
    options = build_welcome_options(True)
    labels = [option.label for option in options]
    assert "Iniciar pipeline de spec" in labels
    assert any(option.argv == ["init", "--force"] for option in options)


def test_prompt_welcome_action_non_tty(monkeypatch):
    monkeypatch.setattr("pulse.terminal.menu.is_interactive", lambda: False)
    assert prompt_welcome_action(initialized=False) is None


def test_resolve_plan_argv_includes_spec_type(monkeypatch):
    monkeypatch.setattr(
        "pulse.terminal.menu._prompt_spec_type",
        lambda: SPEC_TYPES[0],
    )
    monkeypatch.setattr(
        "pulse.terminal.menu.questionary.text",
        lambda *args, **kwargs: type("Answer", (), {"ask": lambda self: "Meu workflow"})(),
    )
    argv = _resolve_plan_argv()
    assert argv == ["plan", "Meu workflow", "--type", "new-issue"]


def test_resolve_plan_argv_setup_project_skips_prompt(monkeypatch):
    monkeypatch.setattr(
        "pulse.terminal.menu._prompt_spec_type",
        lambda: SPEC_TYPES[2],
    )
    argv = _resolve_plan_argv()
    assert argv == ["plan", "Novo projeto", "--type", "setup-project"]
