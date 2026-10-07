from __future__ import annotations

import os
from pathlib import Path

GLOBAL_CONFIG_DIR = Path.home() / ".pulse"
GLOBAL_DB_FILE = GLOBAL_CONFIG_DIR / "pulse.db"
GLOBAL_CONFIG_FILE = GLOBAL_DB_FILE

LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".dev-orchestrator"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.toml"

PROJECT_CONFIG_DIRNAME = ".pulse"
PROJECT_CONFIG_FILENAME = "pulse.db"


def global_state_dir() -> Path:
    home = os.environ.get("PULSE_HOME")
    if home:
        return Path(home).expanduser()
    db_override = os.environ.get("PULSE_DB")
    if db_override:
        return Path(db_override).expanduser().resolve().parent
    return GLOBAL_CONFIG_DIR


def safe_cwd() -> Path:
    """The current directory, or the Pulse state dir when it cannot be read.

    `os.getcwd()` raises `EPERM` on macOS inside protected folders (e.g. Trash)
    and `ENOENT` once the folder is deleted; the detached daemon hits this when
    its inherited cwd disappears. Falling back to `~/.pulse` leads callers to
    the existing "no project" path instead of crashing the run.
    """
    try:
        return Path.cwd()
    except OSError:
        return global_state_dir()


def global_agents_dir() -> Path:
    return global_state_dir() / "agents"


def worktrees_dir() -> Path:
    """Directory for run worktrees, deliberately outside the repository.

    Inside the project it would need a `.gitignore` entry and nested worktrees
    confuse tools that walk the tree; under `~/.pulse/` it lives with the rest
    of the Pulse state.
    """
    return global_state_dir() / "worktrees"


def project_config_file(root: Path) -> Path:
    return root.resolve()


def find_project_config_file(start: Path | None = None) -> Path | None:
    from pulse.config.project_config import find_project_root

    return find_project_root(start)
