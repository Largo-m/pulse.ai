from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.dom import DOMNode

if TYPE_CHECKING:
    from pulse.tui.app import PulseApp


def pulse_app(node: DOMNode) -> PulseApp:
    """The app hosting `node`, through which one screen opens another.

    Textual types `node.app` as a bare `App`; the screens that navigate are only
    mounted by `PulseApp`, which owns the `open_*` methods.
    """
    return cast("PulseApp", node.app)
