import sys


def is_interactive() -> bool:
    return sys.stdout.isatty() and sys.stderr.isatty()
