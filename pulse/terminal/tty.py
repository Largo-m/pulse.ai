import sys
from typing import Any


def is_interactive() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()


def is_cockpit_stream(stream: Any | None) -> bool:
    return stream is not None and bool(getattr(stream, "cockpit", False))
