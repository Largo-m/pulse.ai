from __future__ import annotations

import argparse
import sys

from pulse import __version__
from pulse.config import global_config_exists
from pulse.onboarding import run_onboarding_wizard
from pulse.terminal.actions import run_menu_action
from pulse.terminal.menu import prompt_welcome_action
from pulse.terminal.tty import is_interactive
from pulse.terminal.welcome import is_pulse_ready, render_welcome


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pulse",
        description="Orquestrador terminal-first de workflows com agentes de IA.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"pulse {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not is_interactive():
        render_welcome()
        return 0

    if not global_config_exists():
        code = run_onboarding_wizard()
        if code != 0:
            return code

    while True:
        initialized = is_pulse_ready()
        render_welcome()
        action = prompt_welcome_action(initialized=initialized)
        if action is None:
            return 0
        code = run_menu_action(action, initialized=initialized)
        if code != 0 and action == "init":
            return code


if __name__ == "__main__":
    raise SystemExit(main())
