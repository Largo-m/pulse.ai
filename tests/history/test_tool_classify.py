from __future__ import annotations

from pulse.history.tool_classify import classify_tool, extract_tool_path
from pulse.tui.state import LogKind


def test_classify_search_read_edit():
    assert classify_tool("Search codebase for pulse") == LogKind.SEARCH
    assert classify_tool("Read pulse/cli.py") == LogKind.READ
    assert classify_tool("Edit pulse/tui/app.py") == LogKind.EDIT
    assert classify_tool("List directory pulse/") == LogKind.LIST
    assert classify_tool("Shell npm test", kind="shell") == LogKind.SHELL


def test_extract_tool_path():
    assert extract_tool_path("Read: pulse/cli.py") == "pulse/cli.py"
    assert extract_tool_path("Search for foo") == "Search for foo"
    assert "stream_renderer.py" in extract_tool_path("Read pulse/presentation/stream_renderer.py")
