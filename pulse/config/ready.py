from __future__ import annotations

from pathlib import Path

from pulse.config import global_config_exists, load_global_config, project_config_exists
from pulse.store.paths import safe_cwd


def is_pulse_ready(cwd: Path | None = None) -> bool:
    if global_config_exists():
        config = load_global_config()
        if config and config.is_onboarded:
            return True
    return project_config_exists(cwd or safe_cwd())
