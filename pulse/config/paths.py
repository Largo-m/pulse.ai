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


def global_agents_dir() -> Path:
    return global_state_dir() / "agents"


def project_config_file(root: Path) -> Path:
    return root.resolve()


def find_project_config_file(start: Path | None = None) -> Path | None:
    from pulse.config.project_config import find_project_root

    return find_project_root(start)
