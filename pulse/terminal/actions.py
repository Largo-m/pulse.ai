from __future__ import annotations

from pathlib import Path

from pulse.onboarding import run_onboarding_wizard
from pulse.terminal.menu import run_plan_flow
from pulse.terminal.settings_menu import run_settings_menu


def run_menu_action(action: str, *, cwd: Path | None = None, initialized: bool = False) -> int:
    if action == "plan":
        return run_plan_flow(cwd=cwd)

    if action == "settings":
        return run_settings_menu(cwd=cwd)

    if action == "init":
        return run_onboarding_wizard(force=initialized)

    if action == "exit":
        return 0

    return 0
