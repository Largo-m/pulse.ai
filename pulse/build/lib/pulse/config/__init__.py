from pulse.config.global_config import (
    GlobalConfig,
    global_config_exists,
    load_global_config,
    mark_onboarding_complete,
    save_global_config,
)
from pulse.config.paths import GLOBAL_CONFIG_DIR, GLOBAL_CONFIG_FILE

__all__ = [
    "GLOBAL_CONFIG_DIR",
    "GLOBAL_CONFIG_FILE",
    "GlobalConfig",
    "global_config_exists",
    "load_global_config",
    "mark_onboarding_complete",
    "save_global_config",
]
