from __future__ import annotations

import argparse

from pulse import __version__
from pulse.config import global_config_exists
from pulse.config.commands import run_config_command
from pulse.doctor import run_doctor
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
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="Wizard de onboarding",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Reconfigurar mesmo com config existente",
    )

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Verificar ambiente",
    )
    doctor_parser.add_argument(
        "--test-acp",
        action="store_true",
        help="Incluir teste de conexão ACP",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Mostrar ou criar config de projeto",
    )
    config_parser.add_argument(
        "config_action",
        nargs="?",
        default="show",
        choices=["show", "init"],
        help="show: config efetiva; init: criar .pulse/config.yaml",
    )
    config_parser.add_argument(
        "--workflow",
        default=None,
        help="Mostrar config efetiva de um workflow",
    )
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        return run_onboarding_wizard(force=args.force)
    if args.command == "doctor":
        return run_doctor(test_acp=args.test_acp)
    if args.command == "config":
        return run_config_command(
            action=args.config_action,
            workflow=args.workflow,
        )

    if not is_interactive():
        render_welcome()
        return 0

    if not global_config_exists():
        code = run_onboarding_wizard()
        if code != 0:
            return code

    from pulse.tui.app import run_pulse_app

    return run_pulse_app()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _dispatch(args)


if __name__ == "__main__":
    raise SystemExit(main())
