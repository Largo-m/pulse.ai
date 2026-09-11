from pathlib import Path

from pulse.plan.new_issue_prompt import (
    approval_is_positive,
    build_design_prompt,
    build_execute_task_prompt,
    build_specify_prompt,
    classify_phase_questionnaire_outcome,
    resolve_new_issue_skill,
)
from pulse.plan.runner import run_plan
from pulse.plan.specify_state import (
    TaskState,
    WorkflowState,
    find_resumable_workflows,
    parse_tasks_from_markdown,
    slugify_feature,
)


def test_resolve_new_issue_skill_returns_skill_dir():
    skill_dir = resolve_new_issue_skill()
    assert skill_dir.name == "tlc-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()


def test_slugify_feature():
    assert slugify_feature("Login com OAuth 2.0!") == "login-com-oauth-20"
    assert slugify_feature("   ") == "feature"


def test_parse_tasks_from_markdown():
    content = """
# Tasks

### T1: Create auth service

**What**: Service

### T2: Add login form [P]

**What**: Form
"""
    tasks = parse_tasks_from_markdown(content)
    assert len(tasks) == 2
    assert tasks[0].task_id == "T1"
    assert tasks[0].title == "Create auth service"
    assert tasks[1].task_id == "T2"
    assert tasks[1].title == "Add login form"


def test_workflow_state_roundtrip(tmp_path: Path):
    state = WorkflowState.create_new(
        feature_slug="auth-login",
        user_prompt="Implementar login",
    )
    state.phases["design"].skip = True
    state.phases["design"].skip_reason = "Escopo direto"
    path = state.save(tmp_path)

    loaded = WorkflowState.load(path)
    assert loaded.feature_slug == "auth-login"
    assert loaded.user_prompt == "Implementar login"
    assert loaded.phases["design"].skip is True
    assert loaded.phases["design"].skip_reason == "Escopo direto"


def test_workflow_state_sync_tasks(tmp_path: Path):
    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    feature_dir = tmp_path / state.feature_dir
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text(
        "### T1: First task\n\n### T2: Second task\n",
        encoding="utf-8",
    )
    state.sync_tasks_from_markdown(feature_dir / "tasks.md")
    assert len(state.tasks) == 2
    assert state.tasks[0].task_id == "T1"
    assert state.tasks[1].title == "Second task"


def test_find_resumable_workflows(tmp_path: Path):
    state = WorkflowState.create_new(feature_slug="wip", user_prompt="WIP")
    state.mark_phase_awaiting_approval("specify")
    state.save(tmp_path)

    found = find_resumable_workflows(tmp_path)
    assert len(found) == 1
    assert found[0].feature_slug == "wip"


def test_build_specify_prompt_enforces_isolation_and_approval():
    skill_dir = resolve_new_issue_skill()
    workspace = Path("/tmp/my-project")
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login OAuth")
    prompt = build_specify_prompt(
        workspace=workspace,
        user_prompt="Login OAuth",
        skill_dir=skill_dir,
        state=state,
    )
    assert "Isolamento" in prompt
    assert "specify.md" in prompt
    assert "workflow.yaml" in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "Login OAuth" in prompt


def test_build_design_prompt_references_spec():
    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_design_prompt(
        workspace=Path("/tmp/proj"),
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
    )
    assert "design.md" in prompt
    assert "spec.md" in prompt


def test_build_execute_task_prompt_single_task():
    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_execute_task_prompt(
        workspace=Path("/tmp/proj"),
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
        task_id="T1",
        task_title="Create service",
        tasks_skipped=False,
    )
    assert "**T1**" in prompt
    assert "somente" in prompt
    assert "T1" in prompt
    assert "desta wave" not in prompt
    assert "outras tasks" in prompt


def test_build_execute_wave_prompt_lists_task():
    from pulse.plan.new_issue_prompt import build_execute_wave_prompt

    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_execute_wave_prompt(
        workspace=Path("/tmp/proj"),
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
        wave_label="Task T1",
        task_lines=["- **T1** — A"],
        task_ids=["T1"],
        parallel=False,
        tasks_skipped=False,
    )
    assert "Task T1" in prompt
    assert "T1" in prompt
    assert "Não implemente outras tasks." in prompt
    assert "status: done" in prompt
    assert "valida os gates" in prompt

def test_classify_phase_questionnaire_outcome():
    assert classify_phase_questionnaire_outcome("→ Sim, aprovar e continuar") == "approve"
    assert classify_phase_questionnaire_outcome("→ Cancelar workflow") == "cancel"
    assert classify_phase_questionnaire_outcome("→ Não, preciso de ajustes") == "adjust"


def test_approval_is_positive():
    assert approval_is_positive("→ Sim, aprovar e continuar")
    assert not approval_is_positive("→ Não, preciso de ajustes")


def test_run_plan_new_issue_delegates(monkeypatch):
    calls: list[str] = []

    def fake_run(*, user_prompt: str, **_kwargs) -> int:
        calls.append(user_prompt)
        return 0

    monkeypatch.setattr("pulse.plan.runner.run_new_issue", fake_run)
    assert run_plan(spec_type_id="new-issue", user_prompt="Nova feature") == 0
    assert calls == ["Nova feature"]


def test_should_run_phase_respects_skip():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    state.phases["design"].skip = True
    assert state.should_run_phase("design") is False
    assert state.should_run_phase("specify") is True


def test_next_phase_after_skipped_design():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    state.phases["design"].skip = True
    assert state.next_phase_after("specify") == "tasks"


def test_mark_task_done():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    state.tasks = [TaskState(task_id="T1", title="A"), TaskState(task_id="T2", title="B")]
    state.mark_task_done("T1")
    assert state.tasks[0].status == "done"
    assert state.tasks[1].status == "pending"
    assert state.current_task_id == "T1"


def test_run_execute_task_marks_done_when_gates_pass(monkeypatch, tmp_path: Path):
    from pulse.plan import new_issue_flow
    from pulse.plan.task_waves import GateResult, TaskSpec

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.tasks = [TaskState(task_id="T1", title="A"), TaskState(task_id="T2", title="B")]
    state.save(tmp_path)

    class FakeRunner:
        def run_isolated_prompt(self, **_kwargs):
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(
        new_issue_flow,
        "run_wave_gates",
        lambda **_kwargs: [
            GateResult(ok=True, command="true", exit_code=0),
        ],
    )

    from rich.console import Console

    code = new_issue_flow._run_execute_task(
        runner=FakeRunner(),
        console=Console(force_terminal=False),
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=resolve_new_issue_skill(),
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T1", title="A", gate_commands=("true",)),
    )
    assert code == 0
    assert state.tasks[0].status == "done"
    assert state.tasks[1].status == "pending"


def test_run_execute_task_keeps_pending_when_gate_fails(monkeypatch, tmp_path: Path):
    from pulse.plan import new_issue_flow
    from pulse.plan.task_waves import GateResult, TaskSpec

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.tasks = [TaskState(task_id="T1", title="A")]
    state.save(tmp_path)

    class FakeRunner:
        def run_isolated_prompt(self, **_kwargs):
            return {"stopReason": "end_turn"}

    monkeypatch.setattr(
        new_issue_flow,
        "run_wave_gates",
        lambda **_kwargs: [GateResult(ok=False, command="false", exit_code=1, output="boom")],
    )

    from rich.console import Console

    code = new_issue_flow._run_execute_task(
        runner=FakeRunner(),
        console=Console(force_terminal=False),
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=resolve_new_issue_skill(),
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T1", title="A", gate_commands=("false",)),
    )
    assert code == 1
    assert state.tasks[0].status == "pending"


def test_sync_stream_phases_marks_completed_and_skipped():
    from pulse.plan import new_issue_flow

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.approve_phase("specify")
    state.mark_phase_skipped("design", "não necessário")
    state.approve_phase("tasks")
    state.current_phase = "execute"

    calls: list[dict[str, object]] = []

    class FakeStream:
        def apply_phase_statuses(self, **kwargs):
            calls.append(kwargs)

    class FakeRunner:
        def __init__(self) -> None:
            self._stream = FakeStream()

    new_issue_flow._sync_stream_phases(FakeRunner(), state)
    assert calls == [
        {
            "done_ids": ["specify", "tasks"],
            "skipped_ids": ["design"],
        }
    ]
