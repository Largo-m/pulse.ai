from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import questionary

from pulse.plan.runner import run_plan
from pulse.plan.spec_types import SPEC_TYPES, SpecType
from pulse.terminal.styles import MENU_STYLE
from pulse.terminal.tty import is_interactive


@dataclass(frozen=True)
class WelcomeOption:
    label: str
    action: str


def build_welcome_options(ready: bool) -> list[WelcomeOption]:
    if ready:
        return [
            WelcomeOption("Iniciar pipeline de spec", "plan"),
            WelcomeOption("Configurações", "settings"),
            WelcomeOption("Sair", "exit"),
        ]

    return [
        WelcomeOption("Configurar Pulse", "init"),
        WelcomeOption("Configurações", "settings"),
        WelcomeOption("Sair", "exit"),
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


def run_plan_flow(*, cwd: Path | None = None) -> int:
    spec_type = _prompt_spec_type()
    if spec_type is None:
        return 0

    if spec_type.id == "setup-project":
        return run_plan(spec_type_id=spec_type.id, user_prompt="Novo projeto")

    if spec_type.id == "analyze-codebase":
        return run_plan(spec_type_id=spec_type.id, user_prompt="Mapear codebase existente")

    prompt = questionary.text(
        "Descreva o workflow:",
        default="",
        style=MENU_STYLE,
    ).ask()
    if prompt is None:
        return 0
    prompt = prompt.strip()
    if not prompt:
        questionary.print("Descrição vazia. Operação cancelada.", style="fg:yellow")
        return 0
    return run_plan(spec_type_id=spec_type.id, user_prompt=prompt)


def prompt_welcome_action(
    *,
    cwd: Path | None = None,
    initialized: bool | None = None,
) -> str | None:
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

    if choice is None or choice.action == "exit":
        return None

    return choice.action
