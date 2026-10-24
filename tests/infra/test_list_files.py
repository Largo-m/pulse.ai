"""`vcs.list_files`: the files a task may mention with `@`, as git sees them.

The list feeds a picker, so it must hold what the user would open in the editor
and leave out what the project ignores (build output, virtualenvs), with paths
relative to the project root, where a run works. Tracked and new files come
apart because a worktree run starts from a commit: only tracked files exist
where it works. A worktree run of a project in a repo subfolder works at the
repo top instead, so these paths miss there until issue #71 keeps the subfolder.
"""

from __future__ import annotations

from pathlib import Path

from pulse import vcs
from tests.infra.test_worktree import make_repo


def test_tracked_and_new_files_are_listed_apart_relative_to_the_root(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / "src").mkdir()
    (repo / "src" / "app.py").write_text("print()\n", encoding="utf-8")

    assert vcs.list_files(repo) == ["README.md"]
    assert vcs.list_files(repo, untracked=True) == ["src/app.py"]


def test_ignored_files_are_left_out(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    (repo / ".gitignore").write_text("build/\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "out.bin").write_text("x", encoding="utf-8")

    assert vcs.list_files(repo, untracked=True) == [".gitignore"]
    assert vcs.list_files(repo) == ["README.md"]


def test_a_project_in_a_subfolder_lists_only_its_own_files(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo")
    project = repo / "service"
    project.mkdir()
    (project / "main.py").write_text("", encoding="utf-8")

    assert vcs.list_files(project, untracked=True) == ["main.py"]
    assert vcs.list_files(project) == []


def test_names_with_spaces_and_accents_come_back_verbatim(tmp_path: Path) -> None:
    """git quotes such names unless asked for NUL-separated output."""
    repo = make_repo(tmp_path / "repo")
    (repo / "notas de reunião.md").write_text("", encoding="utf-8")

    assert "notas de reunião.md" in vcs.list_files(repo, untracked=True)


def test_outside_a_repository_there_is_nothing_to_list(tmp_path: Path) -> None:
    (tmp_path / "loose.txt").write_text("", encoding="utf-8")

    for untracked in (False, True):
        assert vcs.list_files(tmp_path, untracked=untracked) == []
        assert vcs.list_files(tmp_path / "missing", untracked=untracked) == []
