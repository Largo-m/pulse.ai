from __future__ import annotations

import ast
from pathlib import Path

STATE_DIRNAME = ".pulse"


def test_the_state_dir_is_named_in_a_single_module():
    """`~/.pulse` had two definitions (config and daemon) that could drift apart.

    Every layer must read the location from `pulse/store/paths.py`; a second literal
    would let the daemon write its socket where the client never looks.
    """
    package = Path(__file__).resolve().parents[2] / "pulse"
    definers = sorted(
        path.relative_to(package)
        for path in package.rglob("*.py")
        if any(
            isinstance(node, ast.Constant) and node.value == STATE_DIRNAME
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    )

    assert definers == [Path("store/paths.py")]
