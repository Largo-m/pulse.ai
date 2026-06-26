from __future__ import annotations

import argparse
import sys

from pulse import __version__
from pulse.config import global_config_exists
from pulse.doctor import run_doctor
from pulse.onboarding import run_onboarding_wizard
from pulse.plan.runner import run_plan
from pulse.plan.spec_types import SPEC_TYPE_IDS
from pulse.terminal.menu import prompt_welcome_action
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
        help="Wizard de primeiro uso e configuração global",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Reconfigurar mesmo se ~/.dev-orchestrator/config.toml existir",
    )

    doctor_parser = subparsers.add_parser("doctor", help="Verificar ambiente e dependências")
    doctor_parser.add_argument(
        "--test-acp",
        action="store_true",
        help="Executar teste ACP com prompt mínimo",
    )

    agents = subparsers.add_parser("agents", help="Gerenciar agentes ACP")
    agents.add_argument("action", nargs="?", choices=["list"], default="list")

    plan = subparsers.add_parser("plan", help="Iniciar pipeline de spec")
    plan.add_argument("prompt", help="Descrição do workflow")
    plan.add_argument(
        "--type",
        choices=list(SPEC_TYPE_IDS),
        default="new-issue",
        help="Tipo de spec",
    )
    plan.add_argument(
        "--phase",
        choices=["prd", "techspec", "tasks"],
        default="prd",
        help="Fase inicial do pipeline",
    )

    return parser


def _run_command(command: str | None, args: argparse.Namespace) -> int:
    if command == "--help":
        _build_parser().print_help()
        return 0

    if command == "init":
        return run_onboarding_wizard(force=getattr(args, "force", False))

    if command == "doctor":
        return run_doctor(test_acp=getattr(args, "test_acp", False))

    if command == "plan":
        return run_plan(
            spec_type_id=getattr(args, "type", "new-issue"),
            user_prompt=args.prompt,
        )

    print(
        f"[pulse] Comando '{command}' ainda não implementado.",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is not None:
        return _run_command(args.command, args)

    if not global_config_exists() and is_interactive():
        return run_onboarding_wizard()

    initialized = render_welcome()

    if not is_interactive():
        return 0

    selected_argv = prompt_welcome_action(initialized=initialized)
    if selected_argv is None:
        return 0

    if selected_argv == ["--help"]:
        return _run_command("--help", args)

    nested = parser.parse_args(selected_argv)
    return _run_command(nested.command, nested)


if __name__ == "__main__":
    raise SystemExit(main())
