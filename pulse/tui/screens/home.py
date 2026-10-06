from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, OptionList, Static
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from pulse import __version__
from pulse.brand import BANNER, PULSE_LINE, PULSE_WAVE
from pulse.client.active_runs import active_runs, awaiting_runs, held_tail, run_line
from pulse.config import global_config_exists
from pulse.status_labels import status_color, status_icon
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


#: Menu raiz e submenus. São telas do mesmo `OptionList` porque a lista de loops
#: vem do banco e cresce com ele — empilhar tudo na raiz deixaria
#: "Configurações" e "Sair" abaixo de N workflows.
ROOT = "root"
SESSION = "session"
#: As sessões que pararam esperando resposta, para entrar direto numa delas.
ALERTS = "alerts"

#: De quanto em quanto tempo a Home pergunta ao daemon o que está esperando.
#: Três segundos é curto o bastante para a pessoa que acabou de sair do cockpit
#: ver o aviso aparecer, e longo o bastante para não martelar o daemon.
ALERT_POLL_SECONDS = 3.0


def _alert_panel(runs: list[dict[str, Any]]) -> Text:
    """O painel de avisos: quantas sessões esperam e quais são.

    Uma linha por sessão, e não só a contagem: com duas runs vivas, "1 sessão
    precisa de você" não diz qual — e descobrir qual era justamente o que
    obrigava a entrar no histórico e abrir uma por uma.
    """
    tone = status_color("awaiting_input")
    count = len(runs)
    noun = "sessão precisa" if count == 1 else "sessões precisam"
    panel = Text()
    panel.append(f"{status_icon('awaiting_input')} {count} {noun} de você", style=tone)
    for run in runs:
        panel.append(f"\n   {run_line(run, tail=held_tail(run))}", style="#888888")
    return panel


class HomeScreen(Screen[None]):
    BINDINGS = [
        ("q", "quit_app", "Quit"),
        ("escape", "back", "Voltar"),
    ]

    #: Sessões paradas esperando resposta, como o daemon as reportou. Default de
    #: classe para a tela nunca depender de já ter sido montada para saber que
    #: não há aviso nenhum.
    _alerts: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="home-content"):
            yield Static(_HOME_BRAND, classes="home-brand")
            yield Static(
                f"Orquestrador de workflows · v{__version__}",
                classes="home-sub",
            )
            yield Static("", id="home-alerts")
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
        #: Loops que já sabem qual é a tarefa — entram direto, sem pedir texto.
        self._default_prompts: dict[str, str] = {}
        self._alerts = []
        self._refresh_options()
        self.query_one("#workflow-prompt", Input).display = False
        self.query_one("#home-alerts", Static).display = False
        self._poll_alerts()
        self.set_interval(ALERT_POLL_SECONDS, self._poll_alerts)

    def _poll_alerts(self) -> None:
        """Pergunta ao daemon o que está esperando — fora do laço de eventos.

        `awaiting_runs` é HTTP com timeout de dois segundos: rodá-lo aqui
        travaria a tela toda vez que o daemon demorasse. `exclusive` cancela o
        poll anterior, mas thread não para por cancelamento: quem chega atrasado
        confere `is_cancelled` em `_fetch_alerts` e descarta o que trouxe.
        """
        self.run_worker(self._fetch_alerts, exclusive=True, thread=True)

    def _fetch_alerts(self) -> None:
        runs = awaiting_runs()
        # Um poll cancelado que voltasse depois do mais novo pintaria a Home com
        # a resposta velha.
        if get_current_worker().is_cancelled:
            return
        try:
            self.app.call_from_thread(self._apply_alerts, runs)
        except Exception:
            # A tela saiu de cena enquanto o daemon respondia: não há nada para
            # atualizar, e a thread do worker não pode morrer gritando por isso.
            pass

    def _apply_alerts(self, runs: list[dict[str, Any]]) -> None:
        if not self.is_mounted:
            return
        changed = [str(run.get("id") or "") for run in runs] != [
            str(run.get("id") or "") for run in self._alerts
        ]
        self._alerts = runs
        panel = self.query_one("#home-alerts", Static)
        panel.display = bool(runs)
        if runs:
            panel.update(_alert_panel(runs))
        # A lista de avisos some do menu junto com o último aviso: deixar a
        # vista aberta mostrando nada seria um beco sem saída.
        if not runs and self._view == ALERTS:
            self._view = ROOT
            self._refresh_options()
            return
        # Só remonta o menu nas vistas que o aviso muda. Remontar a lista de
        # loops enquanto a pessoa a percorre devolveria o cursor ao topo a cada
        # três segundos.
        if changed and self._view in {ROOT, ALERTS}:
            self._refresh_options()

    def _update_hint(self, workflow_id: str | None = None) -> None:
        """A dica do submenu: o que o loop faz, e as teclas embaixo.

        Duas linhas sempre, mesmo sem descrição (o "← Voltar"): alternar entre
        uma e duas faria a lista pular a cada item destacado.
        """
        description = self._descriptions.get(workflow_id or "", "")
        # Loop com tarefa própria não abre campo nenhum: "Enter inicia" avisa que
        # o Enter já começa a run, em vez de prometer um passo que não vem.
        keys = "Enter inicia" if self._default_prompts.get(workflow_id or "") else "Enter seleciona"
        self.query_one(".home-hint", Static).update(f"{description}\n{keys} · Esc volta")

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
        if self._view == ALERTS:
            for run in self._alerts:
                options.add_option(
                    Option(run_line(run, tail=held_tail(run)), id=f"attach:{run.get('id')}")
                )
            options.add_option(Option("← Voltar", id="back"))
            hint.update("Enter abre a sessão · Esc volta")
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
            self._default_prompts = {
                item.id: item.default_prompt for item in workflows if item.default_prompt
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
            # Primeiro item quando existe: é trabalho parado esperando a pessoa,
            # e tudo que vem abaixo começa trabalho novo.
            if self._alerts:
                count = len(self._alerts)
                noun = "sessão aguardando" if count == 1 else "sessões aguardando"
                options.add_option(Option(f"{count} {noun} você", id="alerts"))
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
            self.action_quit_app()
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
        if action == "alerts":
            self._view = ALERTS
            self._refresh_options()
            self.query_one("#home-options", OptionList).focus()
            return
        if action.startswith("attach:"):
            self._open_waiting_run(action.split(":", 1)[1])
            return
        if action == "back":
            self.action_back()
            return
        if action.startswith("workflow:"):
            workflow_id = action.split(":", 1)[1]
            # "Analisar codebase" e "Setup do projeto" olham o repositório, não
            # um pedido: pedir texto era uma pergunta sem resposta possível.
            default_prompt = self._default_prompts.get(workflow_id, "")
            if default_prompt:
                self.app.open_cockpit(workflow_id, default_prompt)
                return
            self._pending_workflow = workflow_id
            prompt_input = self.query_one("#workflow-prompt", Input)
            prompt_input.display = True
            prompt_input.focus()
            prompt_input.placeholder = "Descreva a tarefa…"

    def _open_waiting_run(self, run_id: str) -> None:
        """Abre a sessão que está esperando, ao vivo — a pergunta continua lá.

        O nome não é `_attach`: esse é um método interno do `Screen` do Textual,
        e sobrescrevê-lo quebra a montagem da tela inteira.

        É a mesma porta que o Histórico usa para run viva: o cockpit anexa pelo
        `run_id`, o replay do daemon devolve a tela como ela estava, e a
        pergunta pendente reabre no fim do replay.
        """
        run = next((item for item in self._alerts if str(item.get("id")) == run_id), None)
        if run is None:
            return
        workspace = str(run.get("workspace") or "").strip()
        self.app.open_cockpit(
            str(run.get("workflow_id") or ""),
            str(run.get("prompt") or ""),
            attach_run_id=run_id,
            workspace=Path(workspace) if workspace else None,
        )

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
        """Sair do CLI não encerra o que está rodando: o motor é outro processo.

        Aqui a pergunta é por **toda** run ativa, e não só pelas que esperam
        alguém como no painel de avisos: quem sai precisa saber de tudo que
        continua rodando em background.
        """
        running = active_runs()
        if running:
            count = len(running)
            noun = "run continua rodando" if count == 1 else "runs continuam rodando"
            self.app.exit(
                message=(
                    f"[pulse] {count} {noun} em background — "
                    "`pulse` → Histórico (ou os avisos da Home) para voltar."
                )
            )
            return
        self.app.exit()

    def on_screen_resume(self) -> None:
        self._refresh_options()
        # Voltar do cockpit é justamente quando a pergunta pode ter ficado para
        # trás: não vale esperar o próximo tique para dizer isso.
        self._poll_alerts()
