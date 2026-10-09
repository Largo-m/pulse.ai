"""`AcpClient` against a real child process, for what a fake `Popen` can't show."""

from __future__ import annotations

import sys
from pathlib import Path

from pulse.acp.client import AcpClient

# More than any OS pipe buffer (64 KiB on Linux and macOS).
_NOISE_BYTES = 1 << 20

_CHATTY_ADAPTER = f"""
import json, os, sys
sys.stderr.write("x" * {_NOISE_BYTES})
sys.stderr.flush()
request = json.loads(sys.stdin.readline())
reply = {{"jsonrpc": "2.0", "id": request["id"], "result": {{"cwd": os.getcwd()}}}}
print(json.dumps(reply), flush=True)
sys.stdin.read()
"""


def test_an_adapter_that_floods_stderr_still_answers(tmp_path: Path):
    """npx and agent CLIs log freely to stderr; nobody reads it in the probe.

    A piped, unread stderr fills up and blocks the adapter before it answers,
    so `pulse doctor` would report a timeout for a working runtime.
    """
    client = AcpClient(
        [sys.executable, "-c", _CHATTY_ADAPTER], cwd=str(tmp_path), timeout_seconds=10
    )
    client.start()
    try:
        result = client.initialize()
    finally:
        client.close()

    assert Path(result["cwd"]).resolve() == tmp_path.resolve()
