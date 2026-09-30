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

    def select_choice(self, prompt, choices, *, title=""):
        self.asked.append(title)
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

    def run_isolated_prompt(self, *, prompt_text: str, **_kwargs) -> dict:
        self.prompts.append(prompt_text)
        return self._next({"stopReason": "end_turn"})

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


def test_a_step_without_approval_only_needs_the_agent_to_finish(
    wired, monkeypatch, tmp_path: Path
):
    make_workflow("demo", steps=[("one", "Um")], requires_approval=False)
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
    assert run_store.list_runs(tmp_path)[0].step("one").status == "done"


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
