from __future__ import annotations

from typing import Any

from pulse.mcp.ask_protocol import SERVER_NAME


def pulse_ask_mcp_server(*, url: str) -> dict[str, Any]:
    return {
        "type": "http",
        "name": SERVER_NAME,
        "url": url,
        "headers": [],
    }
