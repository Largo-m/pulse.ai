from pathlib import Path

from pulse.plan.specify_state import PhaseStatus, WorkflowState, _is_workflow_incomplete


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
