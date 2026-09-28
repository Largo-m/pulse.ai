from pathlib import Path

from pulse.plan.specify_state import (
    PhaseStatus,
    WorkflowState,
    _is_workflow_incomplete,
    find_resumable_workflows,
    list_feature_workflows,
)


def test_is_workflow_incomplete_when_execute_pending():
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    assert _is_workflow_incomplete(state) is True


def test_is_workflow_complete_when_execute_done(tmp_path: Path):
    state = WorkflowState.create_new(feature_slug="f", user_prompt="x")
    for phase in ("specify", "design", "tasks"):
        state.approve_phase(phase)
    state.mark_phase_done("execute")
    assert _is_workflow_incomplete(state) is False


def test_workflow_save_creates_feature_dir(tmp_path: Path):
    state = WorkflowState.create_new(feature_slug="my-feat", user_prompt="test")
    path = state.save(tmp_path)
    assert path.is_file()
    assert (tmp_path / ".pulse/specs/features/my-feat").is_dir()


def test_list_feature_workflows_includes_completed(tmp_path: Path):
    incomplete = WorkflowState.create_new(feature_slug="open-feat", user_prompt="open")
    incomplete.save(tmp_path)
    complete = WorkflowState.create_new(feature_slug="done-feat", user_prompt="done")
    for phase in ("specify", "design", "tasks"):
        complete.approve_phase(phase)
        complete.mark_phase_done(phase)
    complete.mark_phase_done("execute")
    complete.save(tmp_path)

    listed = list_feature_workflows(tmp_path)
    assert {item.feature_slug for item in listed} == {"open-feat", "done-feat"}
    resumable = find_resumable_workflows(tmp_path)
    assert {item.feature_slug for item in resumable} == {"open-feat"}
    assert complete.phases["specify"].status == PhaseStatus.DONE
