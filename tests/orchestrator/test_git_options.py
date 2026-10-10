"""Atomic commits, push and pull request at the end of a run that owns its branch."""

from __future__ import annotations

from pathlib import Path

from pulse.domain.run import RunStatus
from pulse.orchestrator.wording import pull_request_body
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


def test_the_pull_request_body_uses_the_template_and_a_figma_link_from_the_prompt():
    body = pull_request_body(
        prompt="ver https://www.figma.com/file/abc",
        branch="ver",
        commits=["feat: add email validation"],
    )

    assert "#### Descrição:\nver https://www.figma.com/file/abc" in body
    assert "https://www.figma.com/file/abc" in body.split("Link do Figma:", 1)[1]
    assert "- [ ] Changelog Atualizado" in body
    assert "[Uma breve descrição de como testar]" in body


def test_a_delivered_step_commits_only_what_changed_and_publishes_the_branch(tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("implement", "Implementar")],
        requires_approval=False,
        commit_types={"implement": "feat"},
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
