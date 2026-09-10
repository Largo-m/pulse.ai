from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import questionary

from pulse.plan.runner import run_plan
from pulse.plan.spec_types import SPEC_TYPES, SpecType
from pulse.terminal.styles import MENU_STYLE
from pulse.terminal.tty import is_interactive

WORKFLOW_ACTION_PREFIX = "workflow:"


@dataclass(frozen=True)
class WelcomeOption:
    label: str
    action: str


def build_welcome_options(ready: bool) -> list[WelcomeOption]:
    if ready:
        options = [
            WelcomeOption(
                f"{spec_type.label} — {spec_type.description}",
                f"{WORKFLOW_ACTION_PREFIX}{spec_type.id}",
            )
            for spec_type in SPEC_TYPES
        ]
        options.extend(
            [
                WelcomeOption("Configurações", "settings"),
                WelcomeOption("Sair", "exit"),
            ]
        )
        return options

    return [
        WelcomeOption("Configurar Pulse", "init"),
        WelcomeOption("Configurações", "settings"),
        WelcomeOption("Sair", "exit"),
    ]


def parse_workflow_action(action: str) -> str | None:
    if not action.startswith(WORKFLOW_ACTION_PREFIX):
        return None
    return action[len(WORKFLOW_ACTION_PREFIX) :]


def run_workflow(spec_type_id: str, *, cwd: Path | None = None) -> int:
    spec_type = _get_spec_type(spec_type_id)
    if spec_type is None:
        questionary.print(f"Workflow desconhecido: {spec_type_id}", style="fg:red")
        return 1

    if spec_type.id == "setup-project":
        return run_plan(spec_type_id=spec_type.id, user_prompt="Novo projeto")

    if spec_type.id == "analyze-codebase":
        return run_plan(spec_type_id=spec_type.id, user_prompt="Mapear codebase existente")

    if spec_type.id == "fix-bug":
        label = "Descreva a quick task (uma frase: o quê e por quê):"
    else:
        label = "Descreva o que deseja construir:"

    prompt = questionary.text(
        label,
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


def _get_spec_type(spec_type_id: str) -> SpecType | None:
    for spec_type in SPEC_TYPES:
        if spec_type.id == spec_type_id:
            return spec_type
    return None
