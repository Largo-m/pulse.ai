from __future__ import annotations

import sys
from typing import Any


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def is_cockpit_stream(stream: Any | None) -> bool:
    return stream is not None and bool(getattr(stream, "cockpit", False))
