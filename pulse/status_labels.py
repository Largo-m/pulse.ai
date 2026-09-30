"""Vocabulário único de status para tudo que aparece na tela.

Cada camada tem o seu enum (`PhaseStatus` do workflow, `PhaseStatus` do
histórico de eventos, `HistoryStatus` do catálogo) e cada tela inventava o seu
rótulo — o mesmo estado saía como `in progress`, `em curso` ou `in_progress`
dependendo de onde o usuário olhava. Aqui ficam o texto, a cor e o ícone,
indexados pelo valor cru do status, para que a origem não importe.
"""

from __future__ import annotations

from enum import Enum

#: Texto exibido ao usuário. Sempre em português, sempre minúsculo.
STATUS_LABELS: dict[str, str] = {
    "pending": "pendente",
    "in_progress": "executando",
    "running": "executando",
    "awaiting_approval": "precisa de você",
    "approved": "aprovado",
    "blocked": "bloqueado",
    "stopped": "parado",
    "done": "concluído",
    "skipped": "pulado",
    "failed": "falhou",
}

#: Uma cor por estado, legível sobre o fundo preto do cockpit.
STATUS_COLORS: dict[str, str] = {
    "pending": "#888888",
    "in_progress": "#A2D729",
    "running": "#A2D729",
    "awaiting_approval": "#D4AF37",
    "approved": "#7FB069",
    "blocked": "#E8913A",
    "stopped": "#9A8FC7",
    "done": "#7FB069",
    "skipped": "#6C7A89",
    "failed": "#FF8A8A",
}

#: Prefixo na sidebar; o ícone repete a cor para quem enxerga pouca cor.
STATUS_ICONS: dict[str, str] = {
    "pending": "Ⅱ",
    "in_progress": "▸",
    "running": "▸",
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
    """Aceita enum, `in progress` e `in_progress` como o mesmo estado."""
    raw = status.value if isinstance(status, Enum) else status
    return str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")


def status_label(status: str | Enum) -> str:
    key = normalize(status)
    return STATUS_LABELS.get(key, key.replace("_", " "))


def status_color(status: str | Enum) -> str:
    return STATUS_COLORS.get(normalize(status), FALLBACK_COLOR)


def status_icon(status: str | Enum) -> str:
    return STATUS_ICONS.get(normalize(status), FALLBACK_ICON)


#: Maior rótulo, para alinhar colunas sem cortar texto.
LABEL_WIDTH = max(len(label) for label in STATUS_LABELS.values())
