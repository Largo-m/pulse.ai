from __future__ import annotations

from pathlib import Path

from pulse.config import global_config_exists, load_global_config


def is_pulse_ready(cwd: Path | None = None) -> bool:
    if global_config_exists():
        config = load_global_config()
        if config and config.is_onboarded:
            return True
    root = cwd or Path.cwd()
    return (root / ".pulse" / "config.yaml").is_file()
