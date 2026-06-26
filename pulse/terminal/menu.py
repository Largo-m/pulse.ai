from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import questionary

from pulse.plan.spec_types import SPEC_TYPES, SpecType
from pulse.terminal.styles import MENU_STYLE
from pulse.terminal.tty import is_interactive


@dataclass(frozen=True)
class WelcomeOption:
    label: str
    argv: list[str]


def build_welcome_options(ready: bool) -> list[WelcomeOption]:
    if ready:
        return [
            WelcomeOption("Iniciar pipeline de spec", ["plan"]),
            WelcomeOption("Verificar ambiente", ["doctor"]),
            WelcomeOption("Reconfigurar Pulse", ["init", "--force"]),
            WelcomeOption("Ver todos os comandos", ["--help"]),
            WelcomeOption("Sair", []),
        ]

    return [
        WelcomeOption("Configurar Pulse", ["init"]),
        WelcomeOption("Verificar ambiente", ["doctor"]),
        WelcomeOption("Ver todos os comandos", ["--help"]),
        WelcomeOption("Sair", []),
    ]


def _prompt_spec_type() -> SpecType | None:
    return questionary.select(
        "Tipo de spec:",
        choices=[
            questionary.Choice(
                f"{spec_type.label} — {spec_type.description}",
                value=spec_type,
            )
            for spec_type in SPEC_TYPES
        ],
        style=MENU_STYLE,
        use_indicator=True,
        use_shortcuts=True,
    ).ask()


def _resolve_plan_argv() -> list[str] | None:
    spec_type = _prompt_spec_type()
    if spec_type is None:
        return None

    if spec_type.id == "setup-project":
        return ["plan", "Novo projeto", "--type", spec_type.id]

    if spec_type.id == "analyze-codebase":
        return ["plan", "Mapear codebase existente", "--type", spec_type.id]

    prompt = questionary.text(
        "Descreva o workflow:",
        default="",
        style=MENU_STYLE,
    ).ask()
    if prompt is None:
        return None
    prompt = prompt.strip()
    if not prompt:
        questionary.print("Descrição vazia. Operação cancelada.", style="fg:yellow")
        return None
    return ["plan", prompt, "--type", spec_type.id]


def prompt_welcome_action(
    *,
    cwd: Path | None = None,
    initialized: bool | None = None,
) -> list[str] | None:
    if not is_interactive():
        return None

    from pulse.terminal.welcome import is_pulse_ready

    project_ready = initialized if initialized is not None else is_pulse_ready(cwd)
    options = build_welcome_options(project_ready)

    choice = questionary.select(
        "O que deseja fazer?",
        choices=[questionary.Choice(option.label, value=option) for option in options],
        style=MENU_STYLE,
        use_indicator=True,
        use_shortcuts=len(options) <= 9,
    ).ask()

    if choice is None:
        return None

    if not choice.argv:
        return None

    if choice.argv == ["plan"]:
        return _resolve_plan_argv()

    return list(choice.argv)
