from __future__ import annotations

from pathlib import Path

GLOBAL_CONFIG_DIR = Path.home() / ".pulse"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.toml"

LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".dev-orchestrator"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.toml"

PROJECT_CONFIG_DIRNAME = ".pulse"
PROJECT_CONFIG_FILENAME = "config.yaml"


def project_config_file(root: Path) -> Path:
    return root / PROJECT_CONFIG_DIRNAME / PROJECT_CONFIG_FILENAME


def find_project_config_file(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / PROJECT_CONFIG_DIRNAME / PROJECT_CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None
