from __future__ import annotations

from pathlib import Path

from pulse.onboarding import run_onboarding_wizard
from pulse.terminal.menu import parse_workflow_action, run_workflow
from pulse.terminal.settings_menu import run_settings_menu


def run_menu_action(action: str, *, cwd: Path | None = None, initialized: bool = False) -> int:
    workflow_id = parse_workflow_action(action)
    if workflow_id is not None:
        return run_workflow(workflow_id, cwd=cwd)

    if action == "settings":
        return run_settings_menu(cwd=cwd)

    if action == "init":
        return run_onboarding_wizard(force=initialized)

    if action == "exit":
        return 0

    return 0
