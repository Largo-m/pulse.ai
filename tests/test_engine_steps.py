"""O motor: qual agente roda agora, e o que acontece quando um step não fecha."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_workflow

from pulse.orchestrator import engine
from pulse.orchestrator.engine import run_workflow
from pulse.runcontrol import RUN_STOPPED, RunControl
from pulse.store import runs as run_store


class _Stream:
    cockpit = True

    def __init__(self) -> None:
        self.phases: list[str] = []
        self.messages: list[str] = []
        self.statuses: list[dict] = []

    def begin_phase(self, title: str) -> None:
        self.phases.append(title)

    def info(self, title: str) -> None:
        self.messages.append(title)

    def error(self, title: str, reason: str = "") -> None:
        self.messages.append(title)

    def apply_phase_statuses(self, **kwargs) -> None:
        self.statuses.append(kwargs)


class _Prompt:
    """Responde ao menu de retry sempre com a mesma escolha."""

    def __init__(self, choice: str = "stop") -> None:
        self.choice = choice
        self.asked: list[str] = []
        self.prompts: list[str] = []

    def select_choice(self, prompt, choices, *, title=""):
        self.asked.append(title)
        self.prompts.append(prompt)
        return self.choice

    def ask_text(self, prompt, *, title=""):
        return ""


class _Runner:
    """Um `AcpSessionRunner` de mentira: só o que o motor chama."""

    def __init__(self, results: list[dict], *, control: RunControl | None = None) -> None:
        self._results = list(results)
        self.prompts: list[str] = []
        self.agents: list[str] = []
        self.control = control or RunControl()
        self.last_session_id = "sess-1"
        self._stream = _Stream()
        self._prompt_handler = _Prompt()
        self.closed = False
        self.revivals = 0

    def bind_run(self, run_id: str) -> None:
        self.run_id = run_id

    def start(self) -> None:
        pass

    def initialize(self) -> None:
        pass

    def authenticate(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def use_agent(self, agent_id: str, policy: str) -> None:
        self.agents.append(agent_id)

    def run_isolated_phase(self, *, initial_prompt: str, **_kwargs) -> dict:
        self.prompts.append(initial_prompt)
        return self._next({"approved": True})

    def run_isolated_prompt(self, *, prompt_text: str, build_continuation=None, **_kwargs) -> dict:
        """Imita o laço de turnos do runner de verdade, inclusive a continuação.

        Sem isto, a chance que o agente tem de se destravar sozinho não seria
        exercitada por teste nenhum: o motor só a oferece por este callback.
        """
        self.prompts.append(prompt_text)
        result = self._next({"stopReason": "end_turn"})
        parts = [str(result.get("phaseSummary", ""))]
        turn = 0
        while build_continuation is not None:
            follow_up = str(build_continuation(result=result, turn=turn) or "").strip()
            if not follow_up:
                break
            self.prompts.append(follow_up)
            result = self._next({"stopReason": "end_turn"})
            parts.append(str(result.get("phaseSummary", "")))
            # O resumo soma os turnos, como no runner de verdade: é o que faz o
            # bloco do último turno ser o que vale.
            result["phaseSummary"] = "\n\n".join(part for part in parts if part)
            turn += 1
        return result

    def _next(self, default: dict) -> dict:
        """Um resultado da fila — ou a exceção que a sessão levantaria."""
        result = self._results.pop(0) if self._results else default
        if isinstance(result, BaseException):
            raise result
        return result

    def ensure_process(self) -> bool:
        self.revivals += 1
        return True


@pytest.fixture
def wired(monkeypatch, tmp_path: Path):
    """Motor com config resolvida e sem terminal — só o laço de steps."""

    class Resolved:
        workspace_dir = tmp_path
        permission_policy = "ask"
        acp_command = ["agent", "acp"]
        model = "auto"
        agent_name = "cursor"

    monkeypatch.setattr(engine, "is_interactive", lambda: False)
    monkeypatch.setattr(engine, "check_runtime_ready", lambda _runtime: None)
    monkeypatch.setattr(engine, "resolve_config", lambda **_kwargs: Resolved())
    return Resolved


def _install(monkeypatch, runner: _Runner) -> None:
    monkeypatch.setattr(engine, "AcpSessionRunner", lambda *_a, **_k: runner)


def _approved(summary: str = "") -> dict:
    return {"approved": True, "outcome": "approve", "phaseSummary": summary}


def _delivered(summary: str = "feito") -> dict:
    """Turno de um step sem aprovação que declarou a entrega."""
    return {
        "stopReason": "end_turn",
        "phaseSummary": f"{summary}\n\n```pulse:outcome\nstatus: done\n```",
    }


def _blocked(reason: str, *, needs: str = "") -> dict:
    """Turno em que o agente declara que não teve como entregar."""
    lines = ["status: blocked", f"reason: {reason}"]
    if needs:
        lines.append(f"needs: {needs}")
    body = "\n".join(lines)
    return {
        "stopReason": "end_turn",
        "phaseSummary": f"tentei e não deu\n\n```pulse:outcome\n{body}\n```",
    }


def test_steps_run_in_order_and_each_one_is_recorded(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")])
    runner = _Runner([_approved(), _approved(), _approved()])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="fazer algo",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner.agents == ["tester", "tester", "tester"]
    record = run_store.list_runs(tmp_path)[0]
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("one", "done"),
        ("two", "done"),
        ("three", "done"),
    ]
    assert record.status == "completed"


def test_the_prompt_template_is_rendered_with_run_values(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("one", "Um")],
        prompt_template="tarefa: {{user_prompt}} em {{workspace}} (step {{step_id}})",
    )
    runner = _Runner([_approved()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="corrigir login",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert runner.prompts == [f"tarefa: corrigir login em {tmp_path} (step one)"]


def test_a_step_sees_what_the_previous_one_produced(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        prompt_template="{{#if previous_summary}}antes: {{previous_summary}}{{/if}}siga",
    )
    runner = _Runner([_approved("escrevi o plano"), _approved()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert runner.prompts[0] == "siga"
    assert runner.prompts[1] == "antes: escrevi o planosiga"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        ({"approved": True, "outcome": "approve", "phaseSummary": "o review"}, "done"),
        ({"approved": False, "outcome": "skip", "phaseSummary": "o review"}, "skipped"),
    ],
)
def test_a_step_sees_how_the_previous_one_closed(
    wired, monkeypatch, tmp_path: Path, outcome: dict, expected: str
):
    """Pulado e concluído não podem chegar indistinguíveis no step seguinte.

    Sem o status, o pulo que o usuário deu num step só valeria para ele: o
    próximo receberia o mesmo resumo nos dois casos e trabalharia por cima de
    uma entrega que a pessoa acabou de dispensar.
    """
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        prompt_template="anterior: {{previous_status}}",
    )
    runner = _Runner([outcome, _approved()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert runner.prompts[0] == "anterior: "
    assert runner.prompts[1] == f"anterior: {expected}"


def test_a_step_that_is_not_approved_stops_the_run(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = _Runner([{"approved": False, "outcome": "continue"}])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 1
    record = run_store.list_runs(tmp_path)[0]
    assert record.step("one").status == "failed"
    assert record.step("two").status == "pending", "o step seguinte nem chegou a rodar"


def test_retry_runs_the_same_step_again(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um")])
    runner = _Runner([{"approved": False, "outcome": "continue"}, _approved()])
    runner._prompt_handler.choice = "retry"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert len(runner.prompts) == 2
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


def test_a_timeout_offers_retry_instead_of_killing_the_run(
    wired, monkeypatch, tmp_path: Path
):
    """Sessão que estourou o prazo é falha de tentativa, não fim de run."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = _Runner(
        [TimeoutError("o agente ficou 600s sem dar sinal em `session/prompt`"), _approved(), _approved()]
    )
    runner._prompt_handler.choice = "retry"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner._prompt_handler.asked == ["Step Um falhou"]
    # A sessão morta é reerguida antes de refazer, senão o retry só repetiria.
    assert runner.revivals == 1
    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["done", "done"]


def test_a_dead_session_that_the_user_gives_up_on_fails_the_step(
    wired, monkeypatch, tmp_path: Path
):
    """`Parar` fecha a run pelo caminho normal: step falhado, sem exceção."""
    make_workflow("demo", steps=[("one", "Um")])
    runner = _Runner([RuntimeError("o processo do agente encerrou")])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 1
    assert runner.revivals == 0
    record = run_store.list_runs(tmp_path)[0]
    assert record.step("one").status == "failed"
    assert record.status == "failed"


def test_skip_settles_the_step_without_failing_the_run(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = _Runner([{"approved": False, "outcome": "skip"}, _approved()])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert record.step("one").status == "skipped"
    assert record.step("two").status == "done"


def test_a_step_without_approval_closes_when_the_agent_declares_the_outcome(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = _Runner([_delivered("pronto")])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


def test_encerrar_o_turno_nao_basta_mais_para_um_step_contar_como_feito(
    wired, monkeypatch, tmp_path: Path
):
    """A regra antiga — `end_turn` é sucesso — era o buraco inteiro.

    Um agente que respondia "não consigo" encerrava o turno como qualquer
    outro, o step virava `done` e o seguinte rodava em cima do nada.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = _Runner(
        [
            {"stopReason": "end_turn", "phaseSummary": "não consigo: falta a credencial"},
            # A continuação que o motor oferece, e o agente insistindo.
            {"stopReason": "end_turn", "phaseSummary": "continuo sem conseguir"},
        ]
    )
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    record = run_store.list_runs(tmp_path)[0]
    assert record.step("one").status == "blocked"
    assert record.step("two").status == "pending", "a cascata para no step bloqueado"
    assert record.status == "blocked", "bloqueio não é falha"


def test_a_declared_block_stops_the_run_instead_of_cascading(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = _Runner([_blocked("falta a credencial do banco", needs="user")])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    assert runner._prompt_handler.asked == ["Um está bloqueado"]
    assert runner._prompt_handler.prompts == ["falta a credencial do banco"], (
        "o motivo que o agente declarou é o que a pessoa lê"
    )
    assert len(runner.prompts) == 1, "`needs: user` não gasta turno de auto-resolução"
    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["blocked", "pending"]


def test_a_blocked_step_gets_one_shot_at_unblocking_itself(
    wired, monkeypatch, tmp_path: Path
):
    """O que está ao alcance do agente não acorda ninguém.

    Sem `needs`, o motor devolve o bloqueio para o próprio agente uma vez — na
    mesma sessão, para ele não recomeçar do zero — antes de escalar.
    """
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = _Runner(
        [_blocked("o arquivo de config não existe"), _delivered("criei o config e segui")]
    )
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner._prompt_handler.asked == [], "ninguém foi interrompido"
    assert len(runner.prompts) == 2
    assert "Bloqueio declarado" in runner.prompts[1]
    assert "o arquivo de config não existe" in runner.prompts[1]
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


def test_the_agent_gets_only_one_shot_before_the_person_is_called(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = _Runner([_blocked("falta X"), _blocked("continua faltando X")])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    assert len(runner.prompts) == 2, "duas tentativas, não um pingue-pongue"
    assert runner._prompt_handler.prompts == ["continua faltando X"]


def test_a_forgotten_outcome_block_is_asked_for_before_it_becomes_a_block(
    wired, monkeypatch, tmp_path: Path
):
    """Esquecer o bloco é o caso mais comum, e o mais barato de resolver.

    Sem isto, todo agente distraído viraria uma pergunta na tela — que é
    exatamente a fricção que faria o protocolo não valer a pena.
    """
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
    runner = _Runner(
        [{"stopReason": "end_turn", "phaseSummary": "terminei tudo"}, _delivered()]
    )
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner._prompt_handler.asked == []
    assert "Desfecho do step" in runner.prompts[1]
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


def test_skipping_a_blocked_step_records_it_as_skipped_not_done(
    wired, monkeypatch, tmp_path: Path
):
    """O pulo explícito é a diferença: antes ele acontecia disfarçado de `done`."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = _Runner([_blocked("falta acesso", needs="user"), _delivered()])
    runner._prompt_handler.choice = "skip"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["skipped", "done"]


def test_a_step_that_did_not_deliver_does_not_feed_the_next_one(
    wired, monkeypatch, tmp_path: Path
):
    """O resumo envenenado: o próximo step não pode receber "não consegui".

    Ele recebe o resumo do último step que entregou de verdade — aqui, o
    primeiro —, não o do step que travou e foi pulado.
    """
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")],
        requires_approval=False,
        prompt_template="{{#if previous_summary}}antes: {{previous_summary}}{{/if}}siga",
    )
    runner = _Runner(
        [
            _delivered("escrevi o plano"),
            _blocked("não consegui migrar o schema", needs="user"),
            _delivered(),
        ]
    )
    runner._prompt_handler.choice = "skip"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert "não consegui migrar o schema" not in runner.prompts[2]
    assert runner.prompts[2].startswith("antes: escrevi o plano")


def test_requires_outcome_off_brings_the_old_behaviour_back(
    wired, monkeypatch, tmp_path: Path
):
    """A válvula de escape, para workflow que ainda não ensinou o protocolo."""
    make_workflow(
        "demo", steps=[("one", "Um")], requires_approval=False, requires_outcome=False
    )
    runner = _Runner([{"stopReason": "end_turn", "phaseSummary": "pronto"}])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner.prompts == ["x"], "sem protocolo, o prompt fica como o autor escreveu"
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


def test_an_approval_step_keeps_the_person_as_the_only_gate(
    wired, monkeypatch, tmp_path: Path
):
    """Um step tem um portão só: onde há aprovação, quem atesta é a pessoa."""
    make_workflow("demo", steps=[("one", "Um")], requires_approval=True)
    runner = _Runner([_approved("entreguei")])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner.prompts == ["x"], "nada de pedir desfecho onde já há aprovação"


def test_with_nobody_to_ask_a_blocked_run_stops_instead_of_going_on(
    wired, monkeypatch, tmp_path: Path
):
    """CLI, cockpit fechado, run do daemon: o default seguro é parar."""
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")], requires_approval=False)
    runner = _Runner([_blocked("falta acesso", needs="user")])
    runner._prompt_handler = object()  # sem `select_choice`: ninguém para perguntar
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["blocked", "pending"]


def test_resuming_picks_up_at_the_first_unfinished_step(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    first = _Runner([_approved(), {"approved": False, "outcome": "continue"}])
    first._prompt_handler.choice = "stop"
    _install(monkeypatch, first)
    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=first._stream,
        prompt_handler=first._prompt_handler,
        render_header=False,
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    second = _Runner([_approved()])
    _install(monkeypatch, second)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=second._stream,
        prompt_handler=second._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(second.prompts) == 1, "o step já concluído não roda de novo"
    assert len(run_store.list_runs(tmp_path)) == 1, "retomar não cria outra run"


def test_retomar_e_a_unica_porta_de_volta_a_uma_run(wired, monkeypatch, tmp_path: Path):
    """Não há refazer do zero: `run_workflow` nem aceita o parâmetro.

    Uma run que já fechou todos os steps não tem o que rodar ao ser reaberta —
    quem quer o pipeline inteiro de novo começa uma run nova.
    """
    import inspect

    assert "restart" not in inspect.signature(run_workflow).parameters

    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    first = _Runner([_approved(), _approved()])
    _install(monkeypatch, first)
    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=first._stream,
        prompt_handler=first._prompt_handler,
        render_header=False,
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    second = _Runner([_approved(), _approved()])
    _install(monkeypatch, second)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=second._stream,
        prompt_handler=second._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    assert second.prompts == [], "tudo já estava done: nada roda de novo"


def test_stopping_between_steps_ends_the_run_as_stopped(wired, monkeypatch, tmp_path: Path):
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    control = RunControl()
    runner = _Runner([_approved()], control=control)
    _install(monkeypatch, runner)

    original = runner.run_isolated_phase

    def stop_after_first(**kwargs):
        result = original(**kwargs)
        control.stop()
        return result

    runner.run_isolated_phase = stop_after_first

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
        control=control,
    )

    assert code == RUN_STOPPED
    record = run_store.list_runs(tmp_path)[0]
    assert record.status == "stopped"
    assert record.step("one").status == "done", "o que já fechou continua fechado"
    assert record.step("two").status == "pending"


def test_a_broken_template_fails_the_step_instead_of_prompting_a_hole(
    wired, monkeypatch, tmp_path: Path
):
    """Placeholder sem valor vira erro: instrução truncada sairia silenciosa."""
    make_workflow("demo", steps=[("one", "Um")], prompt_template="{{nao_existe}}")
    runner = _Runner([])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 1
    assert runner.prompts == []


def test_an_unexpected_error_also_offers_retry(wired, monkeypatch, tmp_path: Path):
    """Não é só timeout e processo morto: qualquer queda dentro do step pergunta.

    A lista de tipos capturados era (Timeout, Runtime, OSError) — bastava um
    `ValueError` vindo de um stdin já fechado para a run morrer sem menu nenhum
    e deixar o step gravado como "executando".
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = _Runner([ValueError("I/O operation on closed file"), _approved(), _approved()])
    runner._prompt_handler.choice = "retry"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    assert runner._prompt_handler.asked == ["Step Um falhou"]
    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["done", "done"]


def test_a_step_that_failed_is_never_left_as_running(wired, monkeypatch, tmp_path: Path):
    """O banco não pode guardar "executando" depois que a run acabou.

    Era esse estado que fazia a run voltar do histórico sem oferecer retomar
    nem refazer: nenhum step estava pendente, só um parado no meio.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois")])
    runner = _Runner([RuntimeError("o processo do agente encerrou")])
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.status for step in record.steps] == ["failed", "pending"]
    assert record.step("one").ended_at, "falha também fecha o relógio do step"


def test_stopping_inside_a_step_leaves_it_pending_and_resume_only_redoes_it(
    wired, monkeypatch, tmp_path: Path
):
    """Parar no meio do step 2: ele volta a pendente e só ele é refeito.

    É o contrato inteiro do parar/retomar — o step cortado não terminou nem
    falhou, e o step 1, que fechou, não pode rodar de novo ao retomar.
    """
    make_workflow("demo", steps=[("one", "Um"), ("two", "Dois"), ("three", "Três")])
    control = RunControl()
    runner = _Runner([_approved(), {"stopReason": "cancelled"}], control=control)
    _install(monkeypatch, runner)

    original = runner.run_isolated_phase

    def stop_during_second(**kwargs):
        if len(runner.prompts) == 1:
            # O usuário aperta `s` enquanto o step 2 está em voo.
            control.stop()
        return original(**kwargs)

    runner.run_isolated_phase = stop_during_second

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
        control=control,
    )

    assert code == RUN_STOPPED
    assert runner._prompt_handler.asked == [], "parar não passa pelo menu de retry"
    record = run_store.list_runs(tmp_path)[0]
    run_id = record.id
    assert record.status == "stopped"
    assert [step.status for step in record.steps] == ["done", "pending", "pending"]

    # Retomar: run nova sobre o mesmo registro, sem controle parado.
    second = _Runner([_approved(), _approved()])
    _install(monkeypatch, second)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=second._stream,
        prompt_handler=second._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    assert len(second.prompts) == 2, "só os dois pendentes rodam; o que fechou não volta"
    record = run_store.load_run(run_id)
    assert [step.status for step in record.steps] == ["done", "done", "done"]


def _repeating(summary: str = "corrigi") -> dict:
    """Turno de um step que entregou e pede outra volta do laço."""
    return {
        "stopReason": "end_turn",
        "phaseSummary": f"{summary}\n\n```pulse:outcome\nstatus: done\nnext: repeat\n```",
    }


def test_um_step_pode_mandar_a_run_voltar_e_repetir_o_trecho(wired, monkeypatch, tmp_path):
    """O laço: revisa, corrige, revisa de novo — até ninguém pedir mais nada."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    # Volta 1 e 2 pedem outra; a 3ª entrega e fica quieta.
    runner = _Runner(
        [_delivered(), _repeating(), _delivered(), _repeating(), _delivered(), _delivered()]
    )
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    # Cada volta tem registro próprio: reusar o id faria a rodada 2 sobrescrever
    # a 1 e o histórico perderia o que aconteceu.
    assert [step.step_id for step in record.steps] == [
        "review",
        "fix",
        "review#2",
        "fix#2",
        "review#3",
        "fix#3",
    ]
    assert all(step.status == "done" for step in record.steps)
    assert record.step("review#2").label == "Review (2ª rodada)"


def test_sem_pedido_o_laco_roda_uma_vez_so(wired, monkeypatch, tmp_path):
    """`repeat_from` é permissão, não obrigação: quem não pede, não repete."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = _Runner([_delivered(), _delivered()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["review", "fix"]


def test_o_teto_de_rodadas_encerra_o_laco(wired, monkeypatch, tmp_path):
    """Sem teto, um agente que sempre pede mais uma deixa a run sem fim."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix")],
        requires_approval=False,
        repeat=("fix", "review", 2),
    )
    # Pede sempre; o motor é quem para.
    runner = _Runner([_delivered(), _repeating(), _delivered(), _repeating()])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["review", "fix", "review#2", "fix#2"]
    assert record.status == "completed"


def test_o_pedido_de_repetir_nao_vale_onde_o_workflow_nao_declarou_laco(
    wired, monkeypatch, tmp_path
):
    """Um agente não cria laço onde a definição não abriu um."""
    make_workflow(
        "demo",
        steps=[("one", "Um"), ("two", "Dois")],
        requires_approval=False,
    )
    runner = _Runner([_repeating(), _repeating()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["one", "two"]


def test_steps_depois_do_laco_nao_herdam_o_numero_da_rodada(wired, monkeypatch, tmp_path):
    """A numeração é da faixa do laço, não de tudo que vem depois dele."""
    make_workflow(
        "demo",
        steps=[("review", "Review"), ("fix", "Fix"), ("ship", "Ship")],
        requires_approval=False,
        repeat=("fix", "review", 3),
    )
    runner = _Runner([_delivered(), _repeating(), _delivered(), _delivered(), _delivered()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == [
        "review",
        "fix",
        "review#2",
        "fix#2",
        "ship",
    ]
