from pathlib import Path

from pulse.plan.new_issue_prompt import (
    approval_is_positive,
    build_techspec_prompt,
    build_execute_task_prompt,
    build_prd_prompt,
    classify_phase_questionnaire_outcome,
    resolve_new_issue_skill,
)
from pulse.plan.runner import run_plan
from pulse.prompts.ask_question import FREE_TEXT_ANSWER_PREFIX, should_add_other_option
from pulse.plan.workflow_state import (
    TaskState,
    WorkflowState,
    find_resumable_workflows,
    parse_tasks_from_markdown,
    slugify_feature,
)


def test_resolve_new_issue_skill_returns_skill_dir():
    skill_dir = resolve_new_issue_skill()
    assert skill_dir.name == "pulse-spec-driven"
    assert (skill_dir / "SKILL.md").is_file()


def test_slugify_feature():
    assert slugify_feature("Login com OAuth 2.0!") == "login-com-oauth-20"
    assert slugify_feature("   ") == "feature"


def test_parse_tasks_from_markdown_accepts_h2_and_table():
    content = """
## T1: Bootstrap projeto

| ID | Title |
| T2 | Domínio |
"""
    tasks = parse_tasks_from_markdown(content)
    assert [task.task_id for task in tasks] == ["T1"]
    assert tasks[0].title == "Bootstrap projeto"
    table_only = "| ID | Title |\n| T2 | Domínio Task |\n"
    parsed = parse_tasks_from_markdown(table_only)
    assert parsed[0].task_id == "T2"
    assert parsed[0].title == "Domínio Task"


def test_resumable_workflow_reads_tasks_written_as_headings(tmp_path: Path):
    from pulse.plan.workflow_state import PhaseStatus, find_resumable_workflows

    state = WorkflowState.create_new(feature_slug="todoist", user_prompt="app")
    state.approve_phase("prd")
    state.approve_phase("techspec")
    state.approve_phase("tasks")
    state.mark_phase_done("execute")
    state.save(tmp_path)
    tasks = tmp_path / state.feature_dir / "tasks.md"
    tasks.write_text("## T1: Bootstrap projeto\n", encoding="utf-8")
    found = find_resumable_workflows(tmp_path)
    assert len(found) == 1
    assert found[0].tasks[0].task_id == "T1"
    assert found[0].phases["execute"].status == PhaseStatus.DONE


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
    state.phases["techspec"].skip = True
    state.phases["techspec"].skip_reason = "Escopo direto"
    path = state.save(tmp_path)

    loaded = WorkflowState.load(path)
    assert loaded.feature_slug == "auth-login"
    assert loaded.user_prompt == "Implementar login"
    assert loaded.phases["techspec"].skip is True
    assert loaded.phases["techspec"].skip_reason == "Escopo direto"


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
    state.mark_phase_awaiting_approval("prd")
    state.save(tmp_path)

    found = find_resumable_workflows(tmp_path)
    assert len(found) == 1
    assert found[0].feature_slug == "wip"


def test_build_prd_prompt_enforces_isolation_and_approval():
    skill_dir = resolve_new_issue_skill()
    workspace = Path("/tmp/my-project")
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login OAuth")
    prompt = build_prd_prompt(
        workspace=workspace,
        user_prompt="Login OAuth",
        skill_dir=skill_dir,
        state=state,
    )
    assert "## Isolation (mandatory)" in prompt
    assert "PRD.md" in prompt
    assert "workflow.yaml" in prompt
    assert "Preciso de algumas informações antes de continuar." in prompt
    assert "Login OAuth" in prompt


def test_build_techspec_prompt_references_spec():
    skill_dir = resolve_new_issue_skill()
    state = WorkflowState.create_new(feature_slug="auth", user_prompt="Login")
    prompt = build_techspec_prompt(
        workspace=Path("/tmp/proj"),
        user_prompt="Login",
        skill_dir=skill_dir,
        state=state,
    )
    assert "TECHSPEC.md" in prompt
    assert "PRD.md" in prompt


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
    assert "implement **only** this task" in prompt
    assert "T1" in prompt
    assert "desta wave" not in prompt
    assert "Do not implement other tasks" in prompt


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
    assert "Do not implement other tasks." in prompt
    assert "status: done" in prompt
    assert "Pulse validates the gates" in prompt

def test_classify_phase_questionnaire_outcome():
    assert classify_phase_questionnaire_outcome("→ Sim, aprovar e continuar") == "approve"
    assert classify_phase_questionnaire_outcome("→ A) Sim, aprovar e continuar") == "approve"
    assert classify_phase_questionnaire_outcome("→ Cancelar workflow") == "cancel"
    assert classify_phase_questionnaire_outcome("→ Não, preciso de ajustes") == "adjust"
    assert classify_phase_questionnaire_outcome("→ A) Unit (JUnit JVM)") == "continue"


def test_approval_is_positive():
    assert approval_is_positive("→ Sim, aprovar e continuar")
    assert not approval_is_positive("→ Não, preciso de ajustes")
    assert not approval_is_positive("→ A) Unit (JUnit JVM)")
    assert not approval_is_positive("→ A) Sim, usar só unit tests")


def test_free_text_answer_never_approves_the_phase():
    """O que o usuário digita em "Outro" é orientação, não aprovação.

    Antes, o texto livre caía no mesmo match de substring dos rótulos fechados:
    uma instrução que só mencionasse "aprovação" aprovava a fase e o pipeline
    seguia para a próxima etapa sem ninguém ter aprovado nada.
    """
    for text in (
        "pode aprovar",
        "aprovar só depois de revisar a seção de retry",
        "o fluxo de aprovação precisa ficar no techspec",
    ):
        answers = f"→ {FREE_TEXT_ANSWER_PREFIX}{text}"
        assert not approval_is_positive(answers), text
        assert classify_phase_questionnaire_outcome(answers) == "continue", text


def test_phase_approval_question_does_not_get_an_other_option():
    """Aprovar fase é decisão fechada: sim, ajuste ou cancelar.

    O "Outro" era injetado quando o agente reformulava o bloco e deixava de
    citar "Cancelar workflow" — e aí a resposta livre chegava onde o flow
    espera uma das três escolhas.
    """
    prompt = "Aprovar Techspec (.pulse/specs/features/x/TECHSPEC.md) e avançar?"
    assert not should_add_other_option(
        prompt=prompt,
        option_labels=["Sim, aprovar e continuar", "Não, preciso de ajustes (descreva)"],
    )


def test_run_plan_rejects_legacy_ids(monkeypatch):
    monkeypatch.setattr("pulse.plan.runner.run_spec", lambda **_k: 0)
    assert run_plan(spec_type_id="new-issue", user_prompt="Nova feature") == 2
    assert run_plan(spec_type_id="fix-bug", user_prompt="Corrigir bug") == 2


def test_should_run_phase_respects_skip():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    state.phases["techspec"].skip = True
    assert state.should_run_phase("techspec") is False
    assert state.should_run_phase("prd") is True


def test_next_phase_after_skipped_techspec():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    state.phases["techspec"].skip = True
    assert state.next_phase_after("prd") == "tasks"


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


    code = new_issue_flow._run_execute_task(
        runner=FakeRunner(),
        cockpit=False,
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


    code = new_issue_flow._run_execute_task(
        runner=FakeRunner(),
        cockpit=False,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=resolve_new_issue_skill(),
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T1", title="A", gate_commands=("false",)),
    )
    assert code == new_issue_flow.TASK_ABORTED
    assert state.tasks[0].status == "failed"


def test_run_execute_task_retries_then_marks_done(monkeypatch, tmp_path: Path):
    from pulse.plan import new_issue_flow
    from pulse.plan.task_waves import GateResult, TaskSpec

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.tasks = [TaskState(task_id="T1", title="A")]
    state.save(tmp_path)

    class Handler:
        def select_choice(self, _prompt, _choices, *, title=""):
            assert "T1" in title
            return "retry"

    class FakeRunner:
        def __init__(self) -> None:
            self._prompt_handler = Handler()
            self.prompts = 0

        def run_isolated_prompt(self, **_kwargs):
            self.prompts += 1
            if self.prompts == 1:
                return {"stopReason": "error"}
            return {"stopReason": "end_turn"}

    runner = FakeRunner()
    monkeypatch.setattr(
        new_issue_flow,
        "run_wave_gates",
        lambda **_kwargs: [GateResult(ok=True, command="true", exit_code=0)],
    )

    code = new_issue_flow._run_execute_task(
        runner=runner,
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=resolve_new_issue_skill(),
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T1", title="A", gate_commands=("true",)),
    )
    assert code == 0
    assert runner.prompts == 2
    assert state.tasks[0].status == "done"


def test_run_execute_task_does_not_mark_done_without_gate(tmp_path: Path):
    from pulse.plan import new_issue_flow
    from pulse.plan.task_waves import TaskSpec

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.tasks = [TaskState(task_id="T1", title="A")]
    state.save(tmp_path)

    class FakeRunner:
        def run_isolated_prompt(self, **_kwargs):
            return {"stopReason": "end_turn"}

    code = new_issue_flow._run_execute_task(
        runner=FakeRunner(),
        cockpit=True,
        workspace=tmp_path,
        user_prompt="x",
        skill_dir=resolve_new_issue_skill(),
        state=state,
        preferred_model=None,
        tasks_skipped=False,
        spec=TaskSpec(task_id="T1", title="A"),
    )
    assert code == new_issue_flow.TASK_ABORTED
    assert state.tasks[0].status == "failed"


def test_sync_stream_phases_marks_completed_and_skipped():
    from pulse.plan import new_issue_flow

    state = WorkflowState.create_new(feature_slug="feat", user_prompt="x")
    state.approve_phase("prd")
    state.mark_phase_skipped("techspec", "não necessário")
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
            "done_ids": ["prd", "tasks"],
            "skipped_ids": ["techspec"],
            "failed_ids": [],
        }
    ]
