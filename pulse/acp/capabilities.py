from __future__ import annotations

from pulse import __version__

# Pulse does not run terminals for the agent; permission requests whose kind
# names a terminal or shell are rejected unless this changes. `execute`, the
# agent running its own shell, follows the step's policy instead.
CLIENT_RUNS_TERMINAL = False

PULSE_CLIENT_CAPABILITIES: dict[str, object] = {
    "fs": {
        "readTextFile": False,
        "writeTextFile": False,
    },
    "terminal": CLIENT_RUNS_TERMINAL,
    "_meta": {
        "cursor": {
            "interactiveExtensions": ["cursor/ask_question", "cursor/create_plan"],
        }
    },
}

PULSE_CLIENT_INFO: dict[str, str] = {
    "name": "pulse",
    "title": "Pulse",
    "version": __version__,
}
