"""The cockpit reads an artifact only from inside the run's worktree.

Artifact paths come from the agent (`locations[].path`, `rawInput`), so they are
untrusted input (AGENTS.md §6.1). A path that climbs out with `..`, points
elsewhere absolutely, or follows a symlink out of the worktree must not put a
file like `~/.ssh/id_rsa` on screen.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pulse.tui.artifacts import artifact_has_content, read_artifact_markdown

PRIVATE_TEXT = "outside the worktree: never on screen"


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    root = tmp_path / "worktree"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    return root


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    outside = tmp_path / "home" / ".ssh"
    outside.mkdir(parents=True)
    target = outside / "id_rsa"
    target.write_text(PRIVATE_TEXT, encoding="utf-8")
    return target


def _escapes(worktree: Path, secret: Path) -> dict[str, str]:
    (worktree / "link.md").symlink_to(secret)
    (worktree / "keys").symlink_to(secret.parent, target_is_directory=True)
    return {
        "dot-dot": "../home/.ssh/id_rsa",
        "nested dot-dot": "docs/../../home/.ssh/id_rsa",
        "absolute outside": str(secret),
        "file uri outside": f"file://{secret}",
        "symlinked file": "link.md",
        "symlinked folder": "keys/id_rsa",
    }


@pytest.mark.parametrize(
    "case",
    [
        "dot-dot",
        "nested dot-dot",
        "absolute outside",
        "file uri outside",
        "symlinked file",
        "symlinked folder",
    ],
)
def test_a_path_leaving_the_worktree_is_never_read(worktree: Path, secret: Path, case: str):
    path = _escapes(worktree, secret)[case]

    text, mtime, exists = read_artifact_markdown(path, cwd=str(worktree))

    assert (text, mtime, exists) == ("", 0.0, False)
    assert artifact_has_content(path, cwd=str(worktree)) is False


@pytest.mark.parametrize(
    "path",
    ["docs/PLAN.md", "./docs/PLAN.md", "docs/sub/../PLAN.md", "{root}/docs/PLAN.md"],
)
def test_a_path_inside_the_worktree_is_still_read(worktree: Path, path: str):
    """Confinement must not cost the legitimate forms the runtimes report."""
    text, _, exists = read_artifact_markdown(path.format(root=worktree), cwd=str(worktree))

    assert exists is True
    assert text == "# Plan\n"


def test_a_symlink_that_stays_inside_the_worktree_is_read(worktree: Path):
    (worktree / "latest.md").symlink_to(worktree / "docs" / "PLAN.md")

    assert read_artifact_markdown("latest.md", cwd=str(worktree))[0] == "# Plan\n"


def test_without_a_worktree_nothing_is_read(worktree: Path):
    """No root to confine to means no read, not a read relative to the daemon's cwd."""
    absolute = str(worktree / "docs" / "PLAN.md")

    assert read_artifact_markdown(absolute, cwd=None) == ("", 0.0, False)
    assert artifact_has_content(absolute, cwd=None) is False


@pytest.mark.parametrize("path", ["", "   ", "docs/\x00PLAN.md"])
def test_a_malformed_path_is_not_read(worktree: Path, path: str):
    assert read_artifact_markdown(path, cwd=str(worktree)) == ("", 0.0, False)
