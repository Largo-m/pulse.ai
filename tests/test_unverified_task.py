from __future__ import annotations

from types import SimpleNamespace

import pytest

from pulse.plan import new_issue_flow
from pulse.plan.new_issue_flow import _offer_unverified
from pulse.plan.workflow_state import PhaseStatus, WorkflowState
from pulse.plan.task_waves import TaskSpec, parse_task_specs

TASKS_MD = """\
### T1: Com gate no Done when

**Done when**:
- [x] Gate: `./gradlew assembleDebug`

### T2: Com gate inline no Verify

**Verify**: `pytest tests/`

### T3: Com a frase antiga

**Done when**:
- [x] Gate check passes: `npm test`

### T4: Sem gate nenhum

**Done when**:
- [x] revisado por humano
"""


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


def _runner(handler) -> SimpleNamespace:
    return SimpleNamespace(_prompt_handler=handler, _stream=None)


# ------------------------------------------------------- parser de gates


@pytest.mark.parametrize(
    ("task_id", "expected"),
    [
        ("T1", "./gradlew assembleDebug"),
        ("T2", "pytest tests/"),
        ("T3", "npm test"),
    ],
)
def test_gate_is_found_in_every_common_shape(task_id: str, expected: str):
    specs = {spec.task_id: spec for spec in parse_task_specs(TASKS_MD)}

    assert specs[task_id].gate_commands == (expected,)


def test_task_without_any_gate_stays_without_gate():
    specs = {spec.task_id: spec for spec in parse_task_specs(TASKS_MD)}

    assert specs["T4"].gate_commands == ()


# --------------------------------------------- decisão para task sem gate


def test_unverified_never_offers_a_plain_retry():
    """Refazer sem gate repetiria o mesmo resultado — era o loop infinito."""
    handler = _Handler(["stop"])

    _offer_unverified(_runner(handler), "Task T2 sem gate", "sem gate")

    assert handler.choice_calls[0] == ["accept", "guidance", "skip", "stop"]
    assert "retry" not in handler.choice_calls[0]


def test_unverified_can_be_accepted():
    handler = _Handler(["accept"])

    assert _offer_unverified(_runner(handler), "t", "x") == ("accept", "")


def test_unverified_guidance_retries_with_instruction():
    handler = _Handler(["guidance"], ["adicione um gate na tasks.md"])

    assert _offer_unverified(_runner(handler), "t", "x") == (
        "retry",
        "adicione um gate na tasks.md",
    )


def test_unverified_without_a_way_to_ask_stops():
    runner = SimpleNamespace(_prompt_handler=None, _stream=None)

    assert _offer_unverified(runner, "t", "x") == ("stop", "")


# ------------------------------------------------- o laço precisa terminar


def _run_task_loop(monkeypatch, tmp_path, handler, *, attempts_seen: list[int]):
    class Runner:
        def __init__(self) -> None:
            self._prompt_handler = handler
            self._stream = None

        def run_isolated_prompt(self, **_kwargs):
            attempts_seen.append(1)
            if len(attempts_seen) > 20:  # rede de segurança contra loop
                raise AssertionError("laço não terminou")
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(new_issue_flow, "build_execute_task_prompt", lambda **_k: "P")
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_reload_state", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_workflow_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_force_task_pending", lambda *_a, **_k: None)

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    state.save(tmp_path)
    return new_issue_flow._run_execute_task(
        runner=Runner(),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T2", title="sem gate"),
    )


def test_accepting_an_unverified_task_ends_the_loop(monkeypatch, tmp_path):
    attempts: list[int] = []
    handler = _Handler(["accept"])

    code = _run_task_loop(monkeypatch, tmp_path, handler, attempts_seen=attempts)

    assert code == 0
    assert len(attempts) == 1


def test_stopping_an_unverified_task_ends_the_loop(monkeypatch, tmp_path):
    attempts: list[int] = []
    handler = _Handler(["stop"])

    code = _run_task_loop(monkeypatch, tmp_path, handler, attempts_seen=attempts)

    assert code == new_issue_flow.TASK_ABORTED
    assert len(attempts) == 1


def test_guidance_retries_once_then_stops(monkeypatch, tmp_path):
    """Com orientação o laço repete, mas continua terminável."""
    attempts: list[int] = []
    handler = _Handler(["guidance", "stop"], ["adicione o gate"])

    code = _run_task_loop(monkeypatch, tmp_path, handler, attempts_seen=attempts)

    assert code == new_issue_flow.TASK_ABORTED
    assert len(attempts) == 2


def test_accepted_task_is_actually_marked_done(monkeypatch, tmp_path):
    """Aceitar sem verificação precisa gravar `done`, não só sair do laço."""
    from pulse.plan.workflow_state import TaskState

    attempts: list[int] = []
    handler = _Handler(["accept"])

    class Runner:
        def __init__(self) -> None:
            self._prompt_handler = handler
            self._stream = None

        def run_isolated_prompt(self, **_kwargs):
            attempts.append(1)
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(new_issue_flow, "build_execute_task_prompt", lambda **_k: "P")
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_reload_state", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_workflow_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_force_task_pending", lambda *_a, **_k: None)

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    state.tasks = [TaskState(task_id="T2", title="sem gate")]
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
        spec=TaskSpec(task_id="T2", title="sem gate"),
    )

    assert code == 0
    reloaded = WorkflowState.load(tmp_path / state.workflow_path)
    task = next(item for item in reloaded.tasks if item.task_id == "T2")
    assert task.status == PhaseStatus.DONE
