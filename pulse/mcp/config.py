from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pulse.mcp.ask_bridge import SOCKET_ENV


def pulse_ask_mcp_server(*, socket_path: Path) -> dict[str, Any]:
    return {
        "type": "stdio",
        "name": "pulse-ask",
        "command": sys.executable,
        "args": ["-m", "pulse.mcp.ask_stdio"],
        "env": [
            {"name": SOCKET_ENV, "value": str(socket_path)},
            {"name": "PYTHONPATH", "value": _pythonpath()},
        ],
    }


def _pythonpath() -> str:
    pulse_root = Path(__file__).resolve().parents[1]
    package_parent = pulse_root.parent
    existing = sys.path if hasattr(sys, "path") else []
    parts = [str(package_parent)]
    for entry in existing:
        if entry and entry not in parts:
            parts.append(entry)
    return ":".join(parts)
