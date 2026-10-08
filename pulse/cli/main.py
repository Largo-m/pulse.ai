from __future__ import annotations

import argparse

from pulse import __version__
from pulse.cli.daemon_command import run_daemon_command
from pulse.client.engine_client import EngineClient
from pulse.config import global_config_exists
from pulse.config.commands import run_config_command
from pulse.doctor import run_doctor
from pulse.orchestrator.tty import is_interactive
from pulse.tui.brand import BANNER, PULSE_LINE, PULSE_WAVE


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
    doctor_parser.add_argument(
        "--local",
        action="store_true",
        help="Rodar checks localmente sem daemon",
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
        help="show: config efetiva; init: registrar projeto no SQLite",
    )
    config_parser.add_argument(
        "--workflow",
        default=None,
        help="Mostrar config efetiva de um workflow",
    )

    daemon_parser = subparsers.add_parser(
        "daemon",
        help="Controlar o Pulse Engine",
    )
    daemon_parser.add_argument(
        "daemon_action",
        choices=["start", "stop", "status"],
        help="start | stop | status",
    )
    return parser


def _print_plain_welcome() -> None:
    print(BANNER.strip("\n"))
    print(PULSE_LINE)
    print(PULSE_WAVE)
    print(f"Pulse v{__version__}")
    print("Rode `pulse` em um terminal interativo para abrir a TUI.")


def _doctor_via_engine(*, test_acp: bool) -> int:
    client = EngineClient()
    try:
        client.ensure_daemon()
        payload = client.doctor()
        checks = payload.get("checks") or []
        failed = False
        for item in checks:
            status = str(item.get("status", ""))
            name = str(item.get("name", ""))
            message = str(item.get("message", ""))
            mark = {"ok": "ok", "warn": "warn"}.get(status, "FAIL")
            print(f"[{mark}] {name}: {message}")
            if status == "fail":
                failed = True
        if test_acp:
            probe = client.post("/api/doctor/acp-probe", {})
            print(f"[{'ok' if probe.get('ok') else 'FAIL'}] ACP: {probe.get('message')}")
            if not probe.get("ok"):
                failed = True
        return 1 if failed else 0
    except Exception as error:
        print(f"[pulse] Engine indisponível ({error}); usando doctor local")
        return run_doctor(test_acp=test_acp)
    finally:
        client.close()


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "init":
        from pulse.tui.app import run_onboarding_app

        return run_onboarding_app(force=args.force)
    if args.command == "doctor":
        if getattr(args, "local", False):
            return run_doctor(test_acp=args.test_acp)
        return _doctor_via_engine(test_acp=args.test_acp)
    if args.command == "config":
        return run_config_command(
            action=args.config_action,
            workflow=args.workflow,
        )
    if args.command == "daemon":
        return run_daemon_command(args.daemon_action)

    if not is_interactive():
        _print_plain_welcome()
        return 0

    if not global_config_exists():
        from pulse.tui.app import run_onboarding_app

        code = run_onboarding_app()
        if code != 0:
            return code

    client = EngineClient()
    try:
        client.ensure_daemon()
    except Exception as error:
        print(f"[pulse] Aviso: não foi possível iniciar o engine ({error})")
    finally:
        client.close()

    from pulse.tui.app import run_pulse_app

    return run_pulse_app()


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _dispatch(args)


if __name__ == "__main__":
    raise SystemExit(main())
