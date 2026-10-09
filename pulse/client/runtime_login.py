"""Run a runtime's own login (`cursor-agent login`, `claude /login`) in the user's terminal.

It is the one subprocess the client side starts: the login is interactive and
needs the terminal the user is sitting at, which the detached daemon does not
have. The argv comes from the daemon's runtime registry (`GET /api/runtimes`),
where it is a class constant, never text the user or an agent typed.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

LOGIN_FAILED = 1


def run_login(command: Sequence[str]) -> int:
    """The login's exit code; a missing command or binary is a failed login."""
    if not command:
        return LOGIN_FAILED
    try:
        # Interactive, so no timeout; argv is the runtime's registered login_command.
        return subprocess.run(list(command), check=False).returncode  # noqa: S603
    except OSError:
        return LOGIN_FAILED
