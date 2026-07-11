from __future__ import annotations

from pathlib import Path

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

from pulse import __version__
from pulse.config import global_config_exists, load_global_config
from pulse.terminal.tty import is_interactive

BANNER = r"""
 ____  _   _ ____  _____ ____
|  _ \| | | / ___|| ____/ ___|
| |_) | | | \___ \|  _| \___ \
|  __/| |_| |___) | |___ ___) |
|_|    \___/|____/|_____|____/
"""

PULSE_LINE = "    ╭──╮      ╭──╮      ╭──╮      ╭──╮"
PULSE_WAVE = "────╯  ╰────╯  ╰────╯  ╰────╯  ╰────"


def _project_initialized(cwd: Path | None = None) -> bool:
    root = cwd or Path.cwd()
    return (root / ".pulse" / "config.yaml").is_file()


def is_pulse_ready(cwd: Path | None = None) -> bool:
    if global_config_exists():
        config = load_global_config()
        if config and config.is_onboarded:
            return True
    return _project_initialized(cwd)


def _build_header(version: str, interactive: bool) -> Group:
    logo = Text(BANNER.strip("\n"), style="bold cyan" if interactive else "")
    pulse = Text()
    pulse.append(PULSE_LINE + "\n", style="dim cyan" if interactive else "")
    pulse.append(PULSE_WAVE, style="bold magenta" if interactive else "")

    subtitle = Text()
    subtitle.append("Orquestrador de workflows com agentes de IA", style="italic")
    subtitle.append(f"  ·  v{version}", style="dim")

    return Group(Align.center(logo), Align.center(pulse), Align.center(subtitle), "")


def _build_status(ready: bool, interactive: bool) -> Text:
    status = Text()
    if ready:
        status.append("✓ ", style="bold green" if interactive else "")
        status.append("Pulse configurado", style="green" if interactive else "")
        config = load_global_config()
        if config and config.is_onboarded:
            status.append(f"  ·  modelo {config.model}", style="dim")
        return status

    status.append("○ ", style="bold yellow" if interactive else "")
    status.append("Primeiro uso — escolha ", style="dim")
    status.append("Configurar Pulse", style="bold cyan" if interactive else "")
    status.append(" para começar", style="dim")
    return status


def render_welcome(
    *,
    cwd: Path | None = None,
    console: Console | None = None,
) -> bool:
    interactive = is_interactive()
    output = console or Console(
        force_terminal=interactive,
        highlight=False,
        soft_wrap=True,
    )
    ready = is_pulse_ready(cwd)
    header = _build_header(__version__, interactive)
    status = _build_status(ready, interactive)

    if interactive:
        hint = Text("Use ↑ ↓ e Enter para escolher  ·  Esc para sair", style="dim")
        body = Group(status, "", hint)
    else:
        from pulse.terminal.menu import build_welcome_options

        lines = Text("Próximos passos\n", style="bold")
        for option in build_welcome_options(ready):
            lines.append(f"  {option.label}\n", style="bold cyan")
        body = Group(status, "", lines)

    panel_kwargs: dict = {
        "title": "[bold]pulse[/bold]" if interactive else "pulse",
        "box": box.ROUNDED,
        "padding": (1, 2),
    }
    if interactive:
        panel_kwargs["border_style"] = "cyan"

    panel = Panel(body, **panel_kwargs)
    output.print(Group(header, panel))
    output.print()
    return ready
