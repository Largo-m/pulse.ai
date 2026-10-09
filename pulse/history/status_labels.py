"""Single status vocabulary (label, color, icon) for everything shown on screen.

Indexed by the raw status value so the same state renders identically whether it
comes from the workflow, event history or catalog enums.
"""

from __future__ import annotations

from enum import Enum

AWAITING_YOU = "precisa de você"
RUNNING = "executando"
STATUS_LABELS: dict[str, str] = {
    "pending": "pendente",
    "in_progress": RUNNING,
    "running": RUNNING,
    "awaiting_input": AWAITING_YOU,
    "awaiting_approval": AWAITING_YOU,
    "approved": "aprovado",
    "blocked": "bloqueado",
    "stopped": "parado",
    "done": "concluído",
    "skipped": "pulado",
    "failed": "falhou",
}

STATUS_COLORS: dict[str, str] = {
    "pending": "#888888",
    "in_progress": "#A2D729",
    "running": "#A2D729",
    "awaiting_input": "#D4AF37",
    "awaiting_approval": "#D4AF37",
    "approved": "#7FB069",
    "blocked": "#E8913A",
    "stopped": "#9A8FC7",
    "done": "#7FB069",
    "skipped": "#6C7A89",
    "failed": "#FF8A8A",
}

STATUS_ICONS: dict[str, str] = {
    "pending": "Ⅱ",
    "in_progress": "▸",
    "running": "▸",
    "awaiting_input": "◆",
    "awaiting_approval": "◆",
    "approved": "✓",
    "blocked": "⊘",
    "stopped": "■",
    "done": "✓",
    "skipped": "⏭",
    "failed": "✗",
}

FALLBACK_COLOR = "#888888"
FALLBACK_ICON = "·"


def normalize(status: str | Enum) -> str:
    """Treat an enum, `in progress` and `in_progress` as the same state."""
    raw = status.value if isinstance(status, Enum) else status
    return str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")


def status_label(status: str | Enum) -> str:
    key = normalize(status)
    return STATUS_LABELS.get(key, key.replace("_", " "))


def status_color(status: str | Enum) -> str:
    return STATUS_COLORS.get(normalize(status), FALLBACK_COLOR)


def status_icon(status: str | Enum) -> str:
    return STATUS_ICONS.get(normalize(status), FALLBACK_ICON)


LABEL_WIDTH = max(len(label) for label in STATUS_LABELS.values())
