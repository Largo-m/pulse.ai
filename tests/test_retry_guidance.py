from __future__ import annotations

from types import SimpleNamespace

from pulse.plan.new_issue_flow import _guidance_block, _offer_retry


class _Handler:
    """Handler de prompt fake: registra o que foi perguntado e devolve o roteiro."""

    def __init__(self, choices: list[str], texts: list[str | None] | None = None) -> None:
        self._choices = list(choices)
        self._texts = list(texts or [])
        self.choice_calls: list[list[tuple[str, str]]] = []
        self.text_calls: list[str] = []

    def select_choice(self, prompt, choices, *, title=""):
        self.choice_calls.append([(label, value) for label, value in choices])
        return self._choices.pop(0) if self._choices else "stop"

    def ask_text(self, prompt, *, title=""):
        self.text_calls.append(prompt)
        return self._texts.pop(0) if self._texts else None


def _runner(handler) -> SimpleNamespace:
    return SimpleNamespace(_prompt_handler=handler, _stream=None)


def test_offers_outro_alongside_retry_and_stop():
    handler = _Handler(["stop"])

    _offer_retry(_runner(handler), "Task T2 falhou", "gate falhou")

    labels = [label for label, _ in handler.choice_calls[0]]
    values = [value for _, value in handler.choice_calls[0]]
    assert values == ["retry", "guidance", "stop"]
    assert any("Outro" in label for label in labels)


def test_retry_carries_no_guidance():
    handler = _Handler(["retry"])

    assert _offer_retry(_runner(handler), "Task T2 falhou", "x") == ("retry", "")


def test_stop_carries_no_guidance():
    handler = _Handler(["stop"])

    assert _offer_retry(_runner(handler), "Task T2 falhou", "x") == ("stop", "")


def test_outro_collects_the_instruction_and_retries():
    handler = _Handler(["guidance"], ["pule o teste de integração e siga"])

    choice, guidance = _offer_retry(_runner(handler), "Task T2 falhou", "gate falhou")

    assert choice == "retry"
    assert guidance == "pule o teste de integração e siga"
    assert handler.text_calls  # perguntou de fato


def test_cancelling_the_text_asks_again_instead_of_stopping():
    """Desistir de escrever não pode virar 'parar' por engano."""
    handler = _Handler(["guidance", "retry"], [None])

    choice, guidance = _offer_retry(_runner(handler), "Task T2 falhou", "x")

    assert choice == "retry"
    assert guidance == ""
    assert len(handler.choice_calls) == 2


def test_blank_text_also_asks_again():
    handler = _Handler(["guidance", "stop"], ["   "])

    choice, _ = _offer_retry(_runner(handler), "Task T2 falhou", "x")

    assert choice == "stop"
    assert len(handler.choice_calls) == 2


def test_stops_when_there_is_no_way_to_ask():
    runner = SimpleNamespace(_prompt_handler=None, _stream=None)

    assert _offer_retry(runner, "Task T2 falhou", "x") == ("stop", "")


def test_handler_without_ask_text_falls_back_to_asking_again():
    class NoText(_Handler):
        ask_text = None

    handler = NoText(["guidance", "stop"])

    choice, _ = _offer_retry(_runner(handler), "Task T2 falhou", "x")

    assert choice == "stop"


def test_guidance_block_reaches_the_agent_with_precedence():
    block = _guidance_block("rode o migrate antes")

    assert "rode o migrate antes" in block
    assert "Orientação do usuário" in block
    assert "precedência" in block


def test_guidance_block_is_empty_without_guidance():
    assert _guidance_block("") == ""
    assert _guidance_block("   ") == ""


def test_guidance_reaches_the_prompt_of_the_next_attempt(tmp_path, monkeypatch):
    """O texto escrito pelo usuário entra no prompt do agente na 2ª tentativa."""
    from pulse.plan import new_issue_flow
    from pulse.plan.workflow_state import WorkflowState
    from pulse.plan.task_waves import TaskSpec

    prompts: list[str] = []

    class Runner:
        def __init__(self, handler) -> None:
            self._prompt_handler = handler
            self._stream = None

        def run_isolated_prompt(self, *, prompt_text, **_kwargs):
            prompts.append(prompt_text)
            # 1ª tentativa falha; 2ª (com orientação) também, para encerrar o laço
            return {"stopReason": "refusal"}

    monkeypatch.setattr(
        new_issue_flow, "build_execute_task_prompt", lambda **_k: "PROMPT BASE"
    )
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_tasks", lambda *_a, **_k: None)

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    state.save(tmp_path)
    # escolhe "Outro", escreve a orientação, depois para
    handler = _Handler(["guidance", "stop"], ["use a lib nova"])

    code = new_issue_flow._run_execute_task(
        runner=Runner(handler),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T2", title="fazer algo"),
    )

    assert code == new_issue_flow.TASK_ABORTED
    assert len(prompts) == 2
    assert "use a lib nova" not in prompts[0]
    assert "use a lib nova" in prompts[1]
    assert "Orientação do usuário" in prompts[1]


def test_text_prompt_round_trips_through_the_engine():
    """Cockpit fala com o daemon: o pedido de texto precisa atravessar o canal."""
    from unittest.mock import MagicMock

    from pulse.client.run_session import EngineRunSession

    class FakeClient:
        def __init__(self) -> None:
            self.answers: list[tuple[str, object]] = []

        def ensure_daemon(self) -> None:
            return None

        def start_run(self, workflow_id, **_kwargs):
            return {"id": "run-1", "workflow_id": workflow_id, "status": "running"}

        def stream_events(self, _run_id):
            yield {
                "type": "prompt.request",
                "id": "t1",
                "kind": "text",
                "payload": {"prompt": "O que fazer?", "title": "Task T2 falhou"},
            }
            yield {"type": "run.finished", "exit_code": 0}

        def answer_prompt(self, prompt_id, answer):
            self.answers.append((prompt_id, answer))
            return {"ok": True}

        def close(self) -> None:
            return None

    handler = MagicMock()
    handler.ask_text.return_value = "rode o migrate antes"
    client = FakeClient()
    session = EngineRunSession(stream=MagicMock(), prompt_handler=handler, client=client)

    assert session.run(workflow_id="spec", user_prompt="x") == 0
    handler.ask_text.assert_called_once()
    assert handler.ask_text.call_args.kwargs["title"] == "Task T2 falhou"
    assert client.answers == [("t1", "rode o migrate antes")]


def test_api_prompt_port_asks_for_text():
    from pulse.daemon.adapters import ApiPromptPort

    class Correlator:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def request(self, kind, payload):
            self.calls.append((kind, payload))
            return "  usar outra abordagem  "

    correlator = Correlator()
    port = ApiPromptPort(correlator)

    assert port.ask_text("O que fazer?", title="Task T2 falhou") == "usar outra abordagem"
    assert correlator.calls[0][0] == "text"
    assert correlator.calls[0][1]["title"] == "Task T2 falhou"


def test_api_prompt_port_text_cancelled():
    from pulse.daemon.adapters import ApiPromptPort

    class Correlator:
        def request(self, kind, payload):
            return None

    assert ApiPromptPort(Correlator()).ask_text("x") is None
