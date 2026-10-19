"""Atomic commits, push and pull request at the end of a run that owns its branch."""

from __future__ import annotations

from pathlib import Path

from pulse.domain.run import RunStatus
from pulse.orchestrator.delivery import pull_request_body
from tests.conftest import make_workflow
from tests.fakes import FakeAgentSession
from tests.orchestrator.harness import EngineHarness, delivered_turn


def _delivered(summary: str = "feito") -> dict[str, object]:
    return {
        "stopReason": "end_turn",
        "phaseSummary": (
            f"{summary}\n\n```pulse:outcome\nstatus: done\ncommit: add email validation\n```"
        ),
    }


def _editing(harness: EngineHarness, session: FakeAgentSession):
    def before(_step_id: str) -> None:
        if session.opened_in is not None:
            harness.workspace.files[session.opened_in] = {"src/app.py": "changed"}
        return None

    return before


def test_the_pull_request_body_renders_the_workflow_template():
    """The body is data on the workflow, so the engine knows no team's template."""
    body = pull_request_body(
        "Tarefa: {{prompt}}\nBranch {{branch}}\n{{commits}}",
        prompt="Corrigir o login",
        branch="corrigir-o-login",
        commits=["feat: add email validation", "fix: keep the session"],
    )

    assert body == (
        "Tarefa: Corrigir o login\nBranch corrigir-o-login\n"
        "- feat: add email validation\n- fix: keep the session"
    )


def test_a_workflow_without_a_template_gets_the_prompt_and_the_commits():
    body = pull_request_body(
        "", prompt="Corrigir o login", branch="b", commits=["feat: add email validation"]
    )

    assert body == "Corrigir o login\n\n- feat: add email validation"


def test_a_delivered_step_commits_only_what_changed_and_publishes_the_branch(tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("implement", "Implementar")],
        requires_approval=False,
        commit_types={"implement": "feat"},
        pull_request_template=(
            "#### Descrição:\n{{prompt}}\n\n{{commits}}\n\n- [ ] Testado localmente"
        ),
    )
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    session = FakeAgentSession([_delivered()])
    session._before_turn = _editing(harness, session)

    code = harness.run(
        session,
        workflow_id="demo",
        user_prompt="Corrigir o login",
        use_worktree=True,
        atomic_commits=True,
        auto_pull_request=True,
    )

    run = harness.runs.only()
    assert code == 0
    assert run.status == RunStatus.COMPLETED
    assert run.worktree_path == ""
    assert run.branch == "corrigir-o-login"
    assert harness.workspace.committed == [
        ("corrigir-o-login", ["src/app.py"], "feat: add email validation")
    ]
    assert harness.workspace.published == ["corrigir-o-login"]
    assert harness.workspace.deleted_branches == ["corrigir-o-login"]
    assert "corrigir-o-login" not in harness.workspace.branches
    body = harness.workspace.requests[0]["body"]
    assert "#### Descrição:\nCorrigir o login" in body
    assert "- feat: add email validation" in body
    assert "- [ ] Testado localmente" in body
    assert "- [x]" not in body
    assert "commit: add email validation" in session.sent[0]


def test_without_atomic_commits_the_worktree_stays_local(tmp_path: Path):
    make_workflow("demo", steps=[("implement", "Implementar")], requires_approval=False)
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    session = FakeAgentSession([delivered_turn()])

    code = harness.run(
        session,
        workflow_id="demo",
        user_prompt="Corrigir o login",
        use_worktree=True,
    )

    run = harness.runs.only()
    assert code == 0
    assert run.worktree_path
    assert harness.workspace.published == []
    assert harness.workspace.committed == []
    assert harness.workspace.requests == []


def test_a_rejected_push_fails_the_run_and_keeps_the_worktree(tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("implement", "Implementar")],
        requires_approval=False,
        commit_types={"implement": "fix"},
    )
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    harness.workspace.fail_push = True
    session = FakeAgentSession([_delivered()])
    session._before_turn = _editing(harness, session)

    code = harness.run(
        session,
        workflow_id="demo",
        user_prompt="Corrigir o login",
        use_worktree=True,
        atomic_commits=True,
    )

    run = harness.runs.only()
    assert code == 1
    assert run.status == RunStatus.FAILED
    assert run.worktree_path
    assert harness.workspace.deleted_branches == []
    assert harness.workspace.requests == []


def test_a_dirty_worktree_is_kept_after_a_successful_push(tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("implement", "Implementar")],
        requires_approval=False,
        commit_types={"implement": "feat"},
    )
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    harness.workspace.dirty = True
    session = FakeAgentSession([_delivered()])
    session._before_turn = _editing(harness, session)

    code = harness.run(
        session,
        workflow_id="demo",
        user_prompt="Corrigir o login",
        use_worktree=True,
        atomic_commits=True,
        auto_pull_request=True,
    )

    run = harness.runs.only()
    assert code == 0
    assert run.worktree_path
    assert harness.workspace.published == ["corrigir-o-login"]
    assert harness.workspace.deleted_branches == []


def test_without_atomic_commits_a_commit_the_agent_made_is_not_pushed(tmp_path: Path):
    """Push sits behind Autocommit: a Worktree-only run never publishes, even when the
    agent ran `git commit` itself, and its worktree and local branch stay.
    """
    make_workflow("demo", steps=[("implement", "Implementar")], requires_approval=False)
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    session = FakeAgentSession([delivered_turn()])

    def agent_commits(_step_id: str) -> None:
        branch = harness.workspace.worktrees[session.opened_in]
        harness.workspace.log.setdefault(branch, []).append("feat: the agent committed")

    session._before_turn = agent_commits

    code = harness.run(
        session, workflow_id="demo", user_prompt="Corrigir o login", use_worktree=True
    )

    run = harness.runs.only()
    assert code == 0
    assert run.worktree_path
    assert harness.workspace.published == []
    assert harness.workspace.deleted_branches == []
    assert harness.workspace.requests == []


def test_a_path_gone_after_the_step_is_left_out_of_its_commit(tmp_path: Path):
    """A leftover file the delivering step deleted has nothing to stage; asking git to
    add it failed the whole commit and lost the step's real change.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Plano"), ("implement", "Implementar")],
        requires_approval=False,
        commit_types={"implement": "feat"},
    )
    harness = EngineHarness(tmp_path)
    harness.workspace = harness.workspace.__class__(tmp_path, repo=True)
    session = FakeAgentSession([delivered_turn(), _delivered()])

    def edit(step_id: str) -> None:
        files = harness.workspace.files
        if step_id == "plan":
            files[session.opened_in] = {"scratch.txt": "notes"}
        else:
            files[session.opened_in] = {"src/app.py": "changed"}

    session._before_turn = edit

    code = harness.run(
        session,
        workflow_id="demo",
        user_prompt="Corrigir o login",
        use_worktree=True,
        atomic_commits=True,
    )

    assert code == 0
    assert harness.workspace.committed == [
        ("corrigir-o-login", ["src/app.py"], "feat: add email validation")
    ]
