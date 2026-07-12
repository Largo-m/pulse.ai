from __future__ import annotations

import argparse
import sys

from pulse import __version__
from pulse.config import global_config_exists
from pulse.onboarding import run_onboarding_wizard
from pulse.terminal.tty import is_interactive
from pulse.terminal.welcome import render_welcome


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
    parser.parse_args(argv)

    if not is_interactive():
        render_welcome()
        return 0

    if not global_config_exists():
        code = run_onboarding_wizard()
        if code != 0:
            return code

    from pulse.tui.app import run_pulse_app

    return run_pulse_app()


if __name__ == "__main__":
    raise SystemExit(main())
