from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option

from pulse import __version__
from pulse.brand import BANNER, PULSE_LINE, PULSE_WAVE
from pulse.config import global_config_exists
from pulse.store.workflow_defs import list_workflows
from pulse.runtime.ready import is_pulse_ready


def _home_brand() -> str:
    logo_lines = BANNER.strip("\n").splitlines()
    wave_lines = (PULSE_LINE, PULSE_WAVE)
    width = max(len(line) for line in (*logo_lines, *wave_lines))
    parts = [line.ljust(width) for line in (*logo_lines, *wave_lines)]
    return "\n".join(parts)


_HOME_BRAND = _home_brand()


def _session_workflows() -> list:
    """Os loops que "Nova sessão" oferece — os pipelines, em ordem alfabética.

    O loop genérico (`is_default`) fica de fora: quem abre este menu quer um
    pipeline, e "Executar" cru só oferecia repassar o prompt ao agente, que é o
    que a pessoa já faria no terminal. Ele continua no banco e na API, para quem
    chama o daemon direto — some da lista, não do produto.
    """
    return sorted(
        (item for item in list_workflows() if not item.is_default),
        key=lambda item: item.label,
    )


#: Menu raiz e submenu de loops. São duas telas do mesmo `OptionList` porque a
#: lista de loops vem do banco e cresce com ele — empilhar tudo na raiz deixaria
#: "Configurações" e "Sair" abaixo de N workflows.
ROOT = "root"
SESSION = "session"


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("escape", "back", "Voltar"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static(_HOME_BRAND, classes="home-brand")
            yield Static(
                f"Orquestrador de workflows · v{__version__}",
                classes="home-sub",
            )
            yield OptionList(id="home-options")
            yield Static("Enter seleciona · Q sai", classes="home-hint")
            yield Input(
                placeholder="Descreva a tarefa…",
                id="workflow-prompt",
                classes="-hidden",
            )
        yield Footer()

    def on_mount(self) -> None:
        self._pending_workflow: str | None = None
        self._view = ROOT
        self._descriptions: dict[str, str] = {}
        self._refresh_options()
        self.query_one("#workflow-prompt", Input).display = False

    def _update_hint(self, workflow_id: str | None = None) -> None:
        """A dica do submenu: o que o loop faz, e as teclas embaixo.

        Duas linhas sempre, mesmo sem descrição (o "← Voltar"): alternar entre
        uma e duas faria a lista pular a cada item destacado.
        """
        description = self._descriptions.get(workflow_id or "", "")
        self.query_one(".home-hint", Static).update(
            f"{description}\nEnter seleciona · Esc volta"
        )

    @on(OptionList.OptionHighlighted, "#home-options")
    def on_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if self._view != SESSION:
            return
        option_id = str(event.option_id or "")
        self._update_hint(
            option_id.split(":", 1)[1] if option_id.startswith("workflow:") else None
        )

    def _refresh_options(self) -> None:
        options = self.query_one("#home-options", OptionList)
        options.clear_options()
        hint = self.query_one(".home-hint", Static)
        if not global_config_exists():
            self._view = ROOT
            options.add_option(Option("Configurar Pulse", id="init"))
            options.add_option(Option("Sair", id="exit"))
            hint.update("Enter seleciona · Q sai")
            return
        if self._view == SESSION:
            workflows = _session_workflows()
            # No item, a descrição curta; na dica, a cadeia de steps. O texto
            # longo em linha dobrava a largura do item e deixava a coluna
            # ilegível — e a cadeia já está em `workflow_steps`, não precisa
            # caber na descrição.
            self._descriptions = {
                item.id: " → ".join(step.label for step in item.steps) for item in workflows
            }
            for workflow in workflows:
                label = workflow.label
                if workflow.description:
                    label = f"{label} · {workflow.description}"
                options.add_option(Option(label, id=f"workflow:{workflow.id}"))
            options.add_option(Option("← Voltar", id="back"))
            self._update_hint(workflows[0].id if workflows else None)
            return
        if is_pulse_ready():
            options.add_option(Option("Nova sessão", id="session"))
            options.add_option(Option("Histórico", id="history"))
        else:
            options.add_option(Option("Configurar Pulse", id="init"))
        options.add_option(Option("Configurações", id="settings"))
        options.add_option(Option("Sair", id="exit"))
        hint.update("Enter seleciona · Q sai")

    @on(OptionList.OptionSelected, "#home-options")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id
        if option_id is None:
            return
        action = str(option_id)
        if action == "exit":
            self.app.exit()
            return
        if action == "init":
            self.app.open_onboarding()
            return
        if action == "settings":
            self.app.open_settings()
            return
        if action == "history":
            self.app.open_history()
            return
        if action == "session":
            self._view = SESSION
            self._refresh_options()
            self.query_one("#home-options", OptionList).focus()
            return
        if action == "back":
            self.action_back()
            return
        if action.startswith("workflow:"):
            self._pending_workflow = action.split(":", 1)[1]
            prompt_input = self.query_one("#workflow-prompt", Input)
            prompt_input.display = True
            prompt_input.focus()
            prompt_input.placeholder = "Descreva a tarefa…"

    def action_back(self) -> None:
        """Esc: fecha o prompt aberto, senão volta ao menu raiz."""
        prompt_input = self.query_one("#workflow-prompt", Input)
        if prompt_input.display:
            prompt_input.value = ""
            prompt_input.display = False
            self._pending_workflow = None
            self.query_one("#home-options", OptionList).focus()
            return
        if self._view == ROOT:
            return
        self._view = ROOT
        self._refresh_options()
        self.query_one("#home-options", OptionList).focus()

    @on(Input.Submitted, "#workflow-prompt")
    def on_prompt_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        workflow_id = self._pending_workflow
        event.input.value = ""
        event.input.display = False
        self._pending_workflow = None
        if not workflow_id or not text:
            return
        self.app.open_cockpit(workflow_id, text)

    def action_quit_app(self) -> None:
        self.app.exit()

    def on_screen_resume(self) -> None:
        self._refresh_options()
