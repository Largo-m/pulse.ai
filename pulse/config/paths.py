from __future__ import annotations

from pathlib import Path

GLOBAL_CONFIG_DIR = Path.home() / ".pulse"
GLOBAL_DB_FILE = GLOBAL_CONFIG_DIR / "pulse.db"
GLOBAL_CONFIG_FILE = GLOBAL_DB_FILE

LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".dev-orchestrator"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.toml"

PROJECT_CONFIG_DIRNAME = ".pulse"
PROJECT_CONFIG_FILENAME = "pulse.db"
PROJECT_SPECS_DIRNAME = f"{PROJECT_CONFIG_DIRNAME}/specs"


def project_specs_dir(root: Path) -> Path:
    return root / PROJECT_CONFIG_DIRNAME / "specs"


def project_config_file(root: Path) -> Path:
    return root.resolve()


def find_project_config_file(start: Path | None = None) -> Path | None:
    from pulse.config.project_config import find_project_root

    return find_project_root(start)
