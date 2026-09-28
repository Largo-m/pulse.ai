from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pulse.plan import analyze_codebase_flow, new_issue_flow, quick_flow, setup_project_flow
from pulse.plan.runner import run_plan
from pulse.runtime.tty import is_cockpit_stream


@dataclass
class _CockpitStream:
    cockpit: bool = True
    errors: list = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def error(self, title: str, reason: str = "") -> None:
        self.errors.append((title, reason))


def test_is_cockpit_stream_detects_flag():
    assert is_cockpit_stream(_CockpitStream()) is True
    assert is_cockpit_stream(_CockpitStream(cockpit=False)) is False
    assert is_cockpit_stream(None) is False
    assert is_cockpit_stream(object()) is False


def test_run_plan_forwards_workspace(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr("pulse.plan.runner.run_setup_project", fake_run)
    code = run_plan(
        spec_type_id="setup-project",
        user_prompt="Novo projeto",
        workspace=tmp_path,
        stream=_CockpitStream(),
        render_header=False,
    )
    assert code == 0
    assert captured["workspace"] == tmp_path
    assert captured["stream"].cockpit is True


@pytest.mark.parametrize(
    ("module", "runner_name", "workflow"),
    [
        (new_issue_flow, "run_new_issue", "new-issue"),
        (quick_flow, "run_quick", "fix-bug"),
        (setup_project_flow, "run_setup_project", "setup-project"),
        (analyze_codebase_flow, "run_analyze_codebase", "analyze-codebase"),
    ],
)
def test_cockpit_bypasses_interactive_gate(module, runner_name, workflow, monkeypatch, tmp_path: Path):
    monkeypatch.setattr(f"{module.__name__}.is_interactive", lambda: False)
    monkeypatch.setattr(f"{module.__name__}.check_runtime_ready", lambda _runtime: None)

    class Resolved:
        workspace_dir = tmp_path
        permission_policy = "ask"
        acp_command = ["agent", "acp"]
        model = "auto"

    monkeypatch.setattr(f"{module.__name__}.resolve_config", lambda **_kwargs: Resolved())
    monkeypatch.setattr(
        f"{module.__name__}.cleanup_legacy_pulse_questions",
        lambda **_kwargs: None,
    )

    if workflow == "new-issue":
        from pulse.plan.workflow_state import WorkflowState

        state = WorkflowState.create_new(feature_slug="demo", user_prompt="x")
        monkeypatch.setattr(f"{module.__name__}.resolve_new_issue_skill", lambda: tmp_path)
        monkeypatch.setattr(f"{module.__name__}._resolve_workflow_state", lambda *_a, **_k: state)
        monkeypatch.setattr(f"{module.__name__}._run_pipeline", lambda **_k: 0)
    elif workflow == "fix-bug":
        monkeypatch.setattr(f"{module.__name__}.resolve_quick_skill", lambda: tmp_path)
        monkeypatch.setattr(f"{module.__name__}.build_quick_plan_prompt", lambda **_k: "prompt")

        class Runner:
            def __init__(self, *_a, **_k):
                pass

            def run_quick(self, **_k):
                return {"stopReason": "end_turn", "approved": True, "outcome": "approve"}

        monkeypatch.setattr(f"{module.__name__}.AcpSessionRunner", Runner)
    elif workflow == "setup-project":
        monkeypatch.setattr(f"{module.__name__}.resolve_tlc_spec_skill", lambda: tmp_path)
        monkeypatch.setattr(f"{module.__name__}.build_setup_project_prompt", lambda **_k: "prompt")

        class Runner:
            def __init__(self, *_a, **_k):
                pass

            def run_setup_project(self, **_k):
                return {"stopReason": "end_turn"}

        monkeypatch.setattr(f"{module.__name__}.AcpSessionRunner", Runner)
    else:
        monkeypatch.setattr(f"{module.__name__}.resolve_analyze_codebase_skill", lambda: tmp_path)
        monkeypatch.setattr(f"{module.__name__}.build_analyze_codebase_prompt", lambda **_k: "prompt")

        class Runner:
            def __init__(self, *_a, **_k):
                pass

            def run_analyze_codebase(self, **_k):
                return {"stopReason": "end_turn"}

        monkeypatch.setattr(f"{module.__name__}.AcpSessionRunner", Runner)

    run = getattr(module, runner_name)
    assert run(user_prompt="x", stream=_CockpitStream(), render_header=False) == 0


@pytest.mark.parametrize(
    ("module", "runner_name"),
    [
        (new_issue_flow, "run_new_issue"),
        (quick_flow, "run_quick"),
        (setup_project_flow, "run_setup_project"),
        (analyze_codebase_flow, "run_analyze_codebase"),
    ],
)
def test_non_cockpit_still_requires_interactive(module, runner_name, monkeypatch):
    monkeypatch.setattr(f"{module.__name__}.is_interactive", lambda: False)
    run = getattr(module, runner_name)
    assert run(user_prompt="x", render_header=False) == 1


@pytest.mark.parametrize(
    ("module", "runner_name"),
    [
        (new_issue_flow, "run_new_issue"),
        (quick_flow, "run_quick"),
        (setup_project_flow, "run_setup_project"),
        (analyze_codebase_flow, "run_analyze_codebase"),
    ],
)
def test_cockpit_surfaces_auth_failures(module, runner_name, monkeypatch):
    monkeypatch.setattr(f"{module.__name__}.is_interactive", lambda: False)
    from pulse.doctor.checks import CheckResult

    monkeypatch.setattr(
        f"{module.__name__}.check_runtime_ready",
        lambda _runtime: CheckResult("Cursor CLI", "fail", "sem agent", "instale o Cursor CLI"),
    )
    run = getattr(module, runner_name)
    with pytest.raises(RuntimeError, match="indisponível"):
        run(user_prompt="x", stream=_CockpitStream(), render_header=False)


def test_analyze_codebase_emits_error_when_questionnaire_cancelled(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(analyze_codebase_flow, "is_interactive", lambda: False)
    monkeypatch.setattr(analyze_codebase_flow, "check_runtime_ready", lambda _runtime: None)

    class Resolved:
        workspace_dir = tmp_path
        permission_policy = "ask"
        acp_command = ["agent", "acp"]
        model = "auto"

    monkeypatch.setattr(analyze_codebase_flow, "resolve_config", lambda **_k: Resolved())
    monkeypatch.setattr(analyze_codebase_flow, "cleanup_legacy_pulse_questions", lambda **_k: None)
    monkeypatch.setattr(analyze_codebase_flow, "resolve_analyze_codebase_skill", lambda: tmp_path)
    monkeypatch.setattr(analyze_codebase_flow, "build_analyze_codebase_prompt", lambda **_k: "prompt")

    class Runner:
        def __init__(self, *_a, **_k):
            pass

        def run_analyze_codebase(self, **_k):
            return {"stopReason": "cancelled"}

    monkeypatch.setattr(analyze_codebase_flow, "AcpSessionRunner", Runner)
    stream = _CockpitStream()
    assert analyze_codebase_flow.run_analyze_codebase(
        user_prompt="x",
        stream=stream,
        render_header=False,
    ) == 1
    assert stream.errors
    assert stream.errors[0][0] == "Questionário cancelado"
