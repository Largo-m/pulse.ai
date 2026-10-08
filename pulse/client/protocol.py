"""The client↔daemon wire contract shared by both sides.

Kept outside `daemon/` so the thin client can read it without importing the
engine (AGENTS.md §2.1). Bump `ENGINE_PROTOCOL` on any change a stale daemon
would serve wrongly: the client restarts a daemon older than this.
"""

from __future__ import annotations

ENGINE_PROTOCOL = 6

REPLAY_END = "stream.replay_end"
PING = "stream.ping"
