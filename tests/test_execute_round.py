"""A Execute não morre na primeira task que falha.

Pular uma task deixa a fase viva: as independentes continuam, as dependentes
ficam bloqueadas, e no fim a run oferece tentar de novo — sem sair do workflow.
"""

from __future__ import annotations

from types import SimpleNamespace

from pulse.plan import new_issue_flow
from pulse.plan.new_issue_flow import _offer_failed_round, _run_task_round
from pulse.plan.specify_state import WorkflowState
from pulse.plan.task_waves import TaskSpec

SPECS = [
    TaskSpec(task_id="T1", title="base"),
    TaskSpec(task_id="T2", title="depende da base", depends_on=("T1",)),
    TaskSpec(task_id="T3", title="independente"),
]


def _round(monkeypatch, tmp_path, results: dict[str, int], *, ran: list[str]):
    def fake_task(*, spec, **_kwargs):
        ran.append(spec.task_id)
        return results.get(spec.task_id, new_issue_flow.TASK_DONE)

    monkeypatch.setattr(new_issue_flow, "_run_execute_task", fake_task)
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    state.save(tmp_path)
    return _run_task_round(
        runner=SimpleNamespace(_prompt_handler=None, _stream=None),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        pending=list(SPECS),
    )


def test_skipped_task_does_not_stop_the_independent_ones(monkeypatch, tmp_path):
    ran: list[str] = []

    outcome, stuck = _round(
        monkeypatch, tmp_path, {"T1": new_issue_flow.TASK_SKIPPED}, ran=ran
    )

    assert outcome == "finished"
    assert ran == ["T1", "T3"]  # T2 depende de T1; T3 não
    assert stuck == [("T1", "falhou"), ("T2", "depende de T1")]


def test_stopping_aborts_the_whole_round(monkeypatch, tmp_path):
    ran: list[str] = []

    outcome, _stuck = _round(
        monkeypatch, tmp_path, {"T1": new_issue_flow.TASK_ABORTED}, ran=ran
    )

    assert outcome == "aborted"
    assert ran == ["T1"]


def test_a_clean_round_leaves_nothing_stuck(monkeypatch, tmp_path):
    ran: list[str] = []

    outcome, stuck = _round(monkeypatch, tmp_path, {}, ran=ran)

    assert (outcome, stuck) == ("finished", [])
    assert ran == ["T1", "T2", "T3"]


# ------------------------------------- a retentativa no fim, dentro da run


class _Handler:
    def __init__(self, choices: list[str]) -> None:
        self._choices = list(choices)
        self.prompts: list[str] = []

    def select_choice(self, prompt, choices, *, title=""):
        self.prompts.append(prompt)
        return self._choices.pop(0) if self._choices else "stop"


def test_failed_round_offers_retry_inside_the_run():
    handler = _Handler(["retry"])
    runner = SimpleNamespace(_prompt_handler=handler, _stream=None)

    choice = _offer_failed_round(runner, [("T2", "falhou"), ("T5", "depende de T2")])

    assert choice == "retry"
    assert "T2 (falhou)" in handler.prompts[0]
    assert "T5 (depende de T2)" in handler.prompts[0]


def test_failed_round_without_a_way_to_ask_stops():
    runner = SimpleNamespace(_prompt_handler=None, _stream=None)

    assert _offer_failed_round(runner, [("T2", "falhou")]) == "stop"


def _execute_phase(monkeypatch, tmp_path, *, rounds: list[int], handler) -> int:
    """Execute com as tasks vindas de um `tasks.md` de verdade."""
    from pulse.plan.specify_state import PhaseStatus, TaskState

    state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
    feature_dir = tmp_path / state.feature_dir
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks.md").write_text(
        "### T1: base\n\n**Done when**:\n- [x] Gate: `pytest`\n", encoding="utf-8"
    )
    state.tasks = [TaskState(task_id="T1", title="base")]
    state.phases["tasks"].status = PhaseStatus.DONE
    state.save(tmp_path)

    attempts: list[str] = []

    def fake_task(*, spec, state, **_kwargs):
        attempts.append(spec.task_id)
        result = rounds[len(attempts) - 1]
        if result == new_issue_flow.TASK_DONE:
            state.mark_task_done(spec.task_id)
        return result

    monkeypatch.setattr(new_issue_flow, "_run_execute_task", fake_task)
    monkeypatch.setattr(new_issue_flow, "print_workflow_result", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_activate_phase_agent", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_tasks", lambda *_a, **_k: None)
    monkeypatch.setattr(new_issue_flow, "_sync_stream_phases", lambda *_a, **_k: None)

    code = new_issue_flow._run_execute_phase(
        runner=SimpleNamespace(_prompt_handler=handler, _stream=None),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=tmp_path,
        state=state,
        preferred_model=None,
    )
    return code, attempts


def test_execute_retries_the_failed_task_without_leaving_the_workflow(monkeypatch, tmp_path):
    """Pulei a task, consertei o ambiente, mandei tentar de novo: acabou ok."""
    handler = _Handler(["retry"])

    code, attempts = _execute_phase(
        monkeypatch,
        tmp_path,
        rounds=[new_issue_flow.TASK_SKIPPED, new_issue_flow.TASK_DONE],
        handler=handler,
    )

    assert code == 0
    assert attempts == ["T1", "T1"]


def test_execute_ends_when_the_user_declines_the_retry(monkeypatch, tmp_path):
    handler = _Handler(["stop"])

    code, attempts = _execute_phase(
        monkeypatch,
        tmp_path,
        rounds=[new_issue_flow.TASK_SKIPPED],
        handler=handler,
    )

    assert code == 1
    assert attempts == ["T1"]
