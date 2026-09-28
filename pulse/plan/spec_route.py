from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pulse.plan.spec_prompt import route_file

_FULL_ALIASES = frozenset({"full", "feature", "new-issue", "pipeline", "prd"})
_QUICK_ALIASES = frozenset({"quick", "fix", "fix-bug", "small", "quick-mode"})


def parse_route_payload(data: Any) -> tuple[str, str] | None:
    if not isinstance(data, dict):
        return None
    raw = str(data.get("flow", "")).strip().lower()
    if raw in _FULL_ALIASES:
        flow = "full"
    elif raw in _QUICK_ALIASES:
        flow = "quick"
    else:
        return None
    reason = str(data.get("reason", "")).strip()
    return flow, reason


def parse_route_text(text: str) -> tuple[str, str] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError:
        return None
    return parse_route_payload(data)


def load_route(workspace: Path) -> tuple[str, str] | None:
    path = route_file(workspace)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_route_text(text)
