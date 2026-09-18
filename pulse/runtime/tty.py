from __future__ import annotations

import sys


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
