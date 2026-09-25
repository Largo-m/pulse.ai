from __future__ import annotations

from types import SimpleNamespace

from pulse.plan import new_issue_flow
from pulse.plan.new_issue_flow import _offer_gate_failure
from pulse.plan.specify_state import PhaseStatus, TaskState, WorkflowState
from pulse.plan.task_waves import GateResult, TaskSpec


class _Handler:
    def __init__(self, choices: list[str], texts: list[str | None] | None = None) -> None:
        self._choices = list(choices)
        self._texts = list(texts or [])
        self.choice_calls: list[list[str]] = []

    def select_choice(self, prompt, choices, *, title=""):
        self.choice_calls.append([value for _label, value in choices])
        return self._choices.pop(0) if self._choices else "stop"

    def ask_text(self, prompt, *, title=""):
        return self._texts.pop(0) if self._texts else None


# ------------------------------------------------ decisão para gate que falhou


def test_gate_failure_offers_a_way_out_that_is_not_retrying():
    """O gate é rodado pelo Pulse: sem "ignorar", refazer só repete a falha."""
    handler = _Handler(["stop"])

    _offer_gate_failure(SimpleNamespace(_prompt_handler=handler, _stream=None), "t", "x")

    assert handler.choice_calls[0] == ["retry", "accept", "guidance", "skip", "stop"]


def test_gate_failure_guidance_retries_with_instruction():
    handler = _Handler(["guidance"], ["pule esse teste"])
    runner = SimpleNamespace(_prompt_handler=handler, _stream=None)

    assert _offer_gate_failure(runner, "t", "x") == ("retry", "pule esse teste")


def test_gate_failure_without_a_way_to_ask_stops():
    runner = SimpleNamespace(_prompt_handler=None, _stream=None)

    assert _offer_gate_failure(runner, "t", "x") == ("stop", "")


# ------------------------------------------------------ o laço precisa terminar


def _run_task_loop(monkeypatch, tmp_path, handler, *, attempts: list[int]):
    """Task com gate que falha sempre — o emulador fora do ar do caso real."""

    class Runner:
        def __init__(self) -> None:
            self._prompt_handler = handler
            self._stream = None

        def run_isolated_prompt(self, **_kwargs):
            attempts.append(1)
            if len(attempts) > 20:  # rede de segurança contra loop
                raise AssertionError("laço não terminou")
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(new_issue_flow, "build_execute_task_prompt", lambda **_k: "P")
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_reload_state", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_workflow_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_force_task_pending", lambda *_a, **_k: None)
    monkeypatch.setattr(
        new_issue_flow,
        "run_wave_gates",
        lambda **_k: [
            GateResult(command="./gradlew connectedDebugAndroidTest", ok=False, exit_code=1, output="")
        ],
    )

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    state.tasks = [TaskState(task_id="T2", title="camada room")]
    state.save(tmp_path)
    code = new_issue_flow._run_execute_task(
        runner=Runner(),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(
            task_id="T2",
            title="camada room",
            gate_commands=("./gradlew connectedDebugAndroidTest",),
        ),
    )
    return code, state


def test_ignoring_a_failing_gate_ends_the_loop_and_marks_done(monkeypatch, tmp_path):
    attempts: list[int] = []

    code, state = _run_task_loop(monkeypatch, tmp_path, _Handler(["accept"]), attempts=attempts)

    assert code == 0
    assert len(attempts) == 1
    reloaded = WorkflowState.load(tmp_path / state.workflow_path)
    task = next(item for item in reloaded.tasks if item.task_id == "T2")
    assert task.status == PhaseStatus.DONE


def test_stopping_on_a_failing_gate_ends_the_loop(monkeypatch, tmp_path):
    attempts: list[int] = []

    code, _state = _run_task_loop(monkeypatch, tmp_path, _Handler(["stop"]), attempts=attempts)

    assert code == new_issue_flow.TASK_ABORTED
    assert len(attempts) == 1


def test_guidance_on_a_failing_gate_retries_then_stays_terminable(monkeypatch, tmp_path):
    attempts: list[int] = []
    handler = _Handler(["guidance", "accept"], ["pule esse teste e siga"])

    code, _state = _run_task_loop(monkeypatch, tmp_path, handler, attempts=attempts)

    assert code == 0
    assert len(attempts) == 2
