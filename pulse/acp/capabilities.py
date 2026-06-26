from __future__ import annotations

from pulse import __version__

PULSE_CLIENT_CAPABILITIES: dict[str, object] = {
    "fs": {
        "readTextFile": False,
        "writeTextFile": False,
    },
    "terminal": False,
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
