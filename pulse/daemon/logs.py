"""The daemon's operational log: what happened to each run, greppable by `run_id`.

The daemon runs detached with stderr appended to `~/.pulse/daemon.log`
(`EngineClient._start_daemon`), so one stderr handler on the `pulse` logger is
the whole setup. Lines read `run.started run_id=… workflow=…`, named after the
SSE events they mirror. Only ids, statuses and timings go here: never a user
prompt, an agent's text or environment contents (AGENTS.md §6.1).
"""

from __future__ import annotations

import logging
import sys
from typing import TextIO

LOGGER = "pulse"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class _DaemonHandler(logging.StreamHandler[TextIO]):
    """Marks the handler this module installed, so configuring twice adds no second one."""


def configure_logging(stream: TextIO | None = None, *, level: int = logging.INFO) -> None:
    """Send Pulse's records to `stream` (stderr by default); calling it again changes nothing."""
    logger = logging.getLogger(LOGGER)
    logger.setLevel(level)
    if any(isinstance(handler, _DaemonHandler) for handler in logger.handlers):
        return
    handler = _DaemonHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)
