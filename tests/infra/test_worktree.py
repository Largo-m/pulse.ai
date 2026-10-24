"""Per-run worktree: the git Pulse speaks, and where the run decides to work."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from pulse import vcs
from pulse.config.project_config import init_project_config, update_project_defaults
from pulse.config.resolved import resolve_config
from pulse.domain.run import RunRecord, StepRecord
from pulse.history.catalog import HistoryCatalog
from pulse.orchestrator.worktree import prepare_workspace
from pulse.store import runs as run_store
from pulse.store.paths import worktrees_dir
from pulse.store.runs import SqliteRunRepository
from pulse.vcs.workspace import GitWorkspace

pytestmark = pytest.mark.skipif(not vcs.git_available(), reason="git is not on PATH")


def make_repo(path: Path) -> Path:
    """Repository with one commit: `worktree add` needs a real HEAD."""
    path.mkdir(parents=True, exist_ok=True)
    # Fixed git argv against a temp repo; git comes from PATH like in production.
    run = lambda *args: subprocess.run(  # noqa: E731, S603 - one-line helper local to this setup
        ["git", *args],  # noqa: S607
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "pulse@example.com")
    run("config", "user.name", "Pulse")
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    run("add", "README.md")
    run("commit", "-q", "-m", "inicial")
    return path


def make_run(workspace: Path, *, run_id: str = "run-1", user_prompt: str = "tarefa") -> RunRecord:
    return run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt=user_prompt,
        steps=[StepRecord(step_id="one", position=1, label="Um", agent_id="tester")],
    )


def prepare(run: RunRecord, root: Path, *, use_worktree: bool) -> tuple[Path, str]:
    """The engine's decision on the production adapters: real git, real database."""
    return prepare_workspace(
        run,
        GitWorkspace(root, worktrees=worktrees_dir()),
        SqliteRunRepository(),
        use_worktree=use_worktree,
    )


def test_repo_root_and_branch(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    assert vcs.repo_root(repo) == repo.resolve()
    assert vcs.current_branch(repo) == "main"


def test_outside_repository_does_not_raise(tmp_path: Path) -> None:
    plain = tmp_path / "sem-git"
    plain.mkdir()
    assert vcs.repo_root(plain) is None
    assert vcs.current_branch(plain) == ""
    assert vcs.is_repo(plain) is False


def test_missing_path_does_not_raise(tmp_path: Path) -> None:
    missing = tmp_path / "nao-existe"
    assert vcs.repo_root(missing) is None
    assert vcs.current_branch(missing) == ""


def test_add_worktree_creates_branch_and_directory(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    branch = vcs.add_worktree(repo, target, "pulse/demo-abc")
    assert branch == "pulse/demo-abc"
    assert (target / "README.md").exists()
    assert vcs.current_branch(target) == "pulse/demo-abc"
    assert vcs.current_branch(repo) == "main"


def test_an_existing_branch_name_is_refused(tmp_path: Path) -> None:
    """A removed worktree leaves its branch behind; the next run must pick another name."""
    repo = make_repo(tmp_path / "repo")
    first = vcs.add_worktree(repo, tmp_path / "wt1", "corrigir-o-login")
    with pytest.raises(vcs.GitError, match="already exists"):
        vcs.add_worktree(repo, tmp_path / "wt2", "corrigir-o-login")
    assert first == "corrigir-o-login"


def test_remove_worktree_refuses_dirty_directory(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    vcs.add_worktree(repo, target, "pulse/demo-abc")
    (target / "novo.txt").write_text("trabalho não salvo\n", encoding="utf-8")

    assert vcs.has_changes(target) is True
    with pytest.raises(vcs.GitError):
        vcs.remove_worktree(repo, target)
    assert target.exists()

    vcs.remove_worktree(repo, target, force=True)
    assert not target.exists()


def test_remove_clean_worktree(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    target = tmp_path / "wt"
    vcs.add_worktree(repo, target, "pulse/demo-abc")
    assert vcs.has_changes(target) is False
    vcs.remove_worktree(repo, target)
    assert not target.exists()


def test_without_isolation_runs_at_root_and_stores_branch(tmp_path: Path) -> None:
    """Toggle off: no worktree, but the branch is still recorded."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)

    exec_dir, branch = prepare(run, repo, use_worktree=False)

    assert exec_dir == repo
    assert branch == "main"
    stored = run_store.load_run(run.id)
    assert stored is not None
    assert stored.worktree_path == ""
    assert stored.branch == "main"


def test_project_outside_git_is_not_isolated(tmp_path: Path) -> None:
    """Toggle on without a repository must not prevent the run."""
    plain = tmp_path / "sem-git"
    plain.mkdir()
    run = make_run(plain)

    exec_dir, branch = prepare(run, plain, use_worktree=True)

    assert exec_dir == plain
    assert branch == ""


def test_isolation_opens_worktree_and_stores_it(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)

    exec_dir, branch = prepare(run, repo, use_worktree=True)

    assert exec_dir == worktrees_dir() / run.id
    assert exec_dir.is_dir()
    assert branch == "tarefa"
    assert vcs.current_branch(exec_dir) == branch
    assert vcs.current_branch(repo) == "main"

    stored = run_store.load_run(run.id)
    assert stored is not None
    assert stored.worktree_path == str(exec_dir)
    assert stored.branch == branch
    assert stored.branch_owned is True
    assert stored.branch_base
    assert stored.workspace_root == str(repo.resolve())
    assert stored.exec_root == str(exec_dir)


def test_resume_reuses_the_run_worktree(tmp_path: Path) -> None:
    """Opening a second worktree would discard what finished steps produced."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, branch = prepare(run, repo, use_worktree=True)
    (first / "entrega.md").write_text("trabalho do step 1\n", encoding="utf-8")

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    second, same_branch = prepare(resumed, repo, use_worktree=True)

    assert second == first
    assert same_branch == branch
    assert (second / "entrega.md").exists()


def commit_in(path: Path, name: str) -> None:
    (path / name).write_text("trabalho de um step\n", encoding="utf-8")
    for args in (["add", name], ["commit", "-q", "-m", name]):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)  # noqa: S603, S607 - fixed git argv on a temp repo


def test_worktree_removed_from_history_reopens_run_branch(tmp_path: Path) -> None:
    """Resuming after `w` continues where the steps stopped, not from HEAD."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, branch = prepare(run, repo, use_worktree=True)
    commit_in(first, "spec.md")

    catalog = HistoryCatalog(repo)
    item = catalog.get(run.id)
    assert item is not None
    assert catalog.remove_worktree(item) is True

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    second, same_branch = prepare(resumed, repo, use_worktree=True)

    assert same_branch == branch
    assert (second / "spec.md").exists()
    assert run_store.load_run(run.id).worktree_path == str(second)


def test_manually_deleted_worktree_reopens_run_branch(tmp_path: Path) -> None:
    """A directory deleted behind git's back must not block resuming the run.

    Git still has the path registered and would refuse `add` there, and each
    refused attempt left a `-N` branch behind.
    """
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, branch = prepare(run, repo, use_worktree=True)
    commit_in(first, "spec.md")
    shutil.rmtree(first)

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    second, same_branch = prepare(resumed, repo, use_worktree=True)

    assert second == first
    assert same_branch == branch
    assert (second / "spec.md").exists()
    assert not vcs.branch_exists(repo, f"{branch}-2")


def test_project_branch_is_not_reattached(tmp_path: Path) -> None:
    """A run started at the root stores `main`; enabling the toggle later opens a new branch."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    prepare(run, repo, use_worktree=False)

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    assert resumed.branch == "main"
    target, branch = prepare(resumed, repo, use_worktree=True)

    assert branch == "tarefa"
    assert target == worktrees_dir() / run.id
    assert vcs.current_branch(repo) == "main"


def test_deleted_run_branch_opens_another(tmp_path: Path) -> None:
    """Without the branch there is nothing to reattach: the run continues from HEAD."""
    repo = make_repo(tmp_path / "repo")
    run = make_run(repo)
    first, branch = prepare(run, repo, use_worktree=True)
    vcs.remove_worktree(repo, first)
    subprocess.run(  # noqa: S603 - fixed git argv on a temp repo
        ["git", "branch", "-D", branch],  # noqa: S607 - git from PATH, as in production
        cwd=repo,
        check=True,
        capture_output=True,
    )

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    second, new_branch = prepare(resumed, repo, use_worktree=True)

    assert second.is_dir()
    assert new_branch == branch


def commit_project_in_subfolder(repo: Path) -> Path:
    project = repo / "service"
    project.mkdir()
    commit_in(project, "main.py")
    return project


def test_a_project_in_a_subfolder_works_in_that_subfolder_of_its_worktree(tmp_path: Path) -> None:
    """Without a worktree the agent works in `repo/service`; with one it worked at the
    top of the repo, so `@main.py`, `{{workspace}}` and artifact paths pointed elsewhere.
    """
    project = commit_project_in_subfolder(make_repo(tmp_path / "repo"))
    run = make_run(project)

    exec_dir, _branch = prepare(run, project, use_worktree=True)

    assert exec_dir == worktrees_dir() / run.id / "service"
    assert (exec_dir / "main.py").is_file()
    stored = run_store.load_run(run.id)
    assert stored is not None
    assert stored.worktree_path == str(exec_dir)
    assert stored.workspace_root == str(project.resolve())


def test_a_reopened_worktree_keeps_the_project_subfolder(tmp_path: Path) -> None:
    project = commit_project_in_subfolder(make_repo(tmp_path / "repo"))
    run = make_run(project)
    first, _branch = prepare(run, project, use_worktree=True)
    shutil.rmtree(worktrees_dir() / run.id)

    resumed = run_store.load_run(run.id)
    assert resumed is not None
    second, _same = prepare(resumed, project, use_worktree=True)

    assert second == first
    assert (second / "main.py").is_file()


def test_an_untracked_project_subfolder_exists_in_the_worktree(tmp_path: Path) -> None:
    """A project folder not committed yet is absent from a fresh checkout; the agent
    still needs it as its working directory.
    """
    repo = make_repo(tmp_path / "repo")
    project = repo / "novo"
    project.mkdir()
    run = make_run(project)

    exec_dir, _branch = prepare(run, project, use_worktree=True)

    assert exec_dir == worktrees_dir() / run.id / "novo"
    assert exec_dir.is_dir()


def test_removing_a_subfolder_run_worktree_removes_the_whole_worktree(tmp_path: Path) -> None:
    project = commit_project_in_subfolder(make_repo(tmp_path / "repo"))
    run = make_run(project)
    prepare(run, project, use_worktree=True)

    catalog = HistoryCatalog(project)
    item = catalog.get(run.id)
    assert item is not None
    assert catalog.remove_worktree(item) is True

    assert not (worktrees_dir() / run.id).exists()


def test_concurrent_runs_do_not_share_directory(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    one, _ = prepare(
        make_run(repo, run_id="run-a", user_prompt="tarefa a"), repo, use_worktree=True
    )
    two, _ = prepare(
        make_run(repo, run_id="run-b", user_prompt="tarefa b"), repo, use_worktree=True
    )
    assert one != two
    assert one.is_dir()
    assert two.is_dir()


def test_project_toggle_reaches_resolved_config(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    init_project_config(repo)
    assert resolve_config(repo).use_worktree is False

    update_project_defaults(repo, use_worktree=True)
    assert resolve_config(repo).use_worktree is True

    update_project_defaults(repo, use_worktree=False)
    assert resolve_config(repo).use_worktree is False


def test_toggle_survives_other_project_edits(tmp_path: Path) -> None:
    """Saving a model must not disable isolation that was turned on."""
    repo = make_repo(tmp_path / "repo")
    update_project_defaults(repo, use_worktree=True)
    update_project_defaults(repo, model="sonnet")
    assert resolve_config(repo).use_worktree is True
