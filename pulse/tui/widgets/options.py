from __future__ import annotations

from typing import TypedDict


class WidgetOptions(TypedDict, total=False):
    """The `textual.widget.Widget` keywords our widgets pass through untouched."""

    name: str | None
    id: str | None
    classes: str | None
    disabled: bool
    markup: bool
