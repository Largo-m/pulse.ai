from __future__ import annotations

from pulse.tui.state import LogKind
from pulse.tui.tool_detail import build_tool_labels, extract_tool_target, shorten_path, summarize_content


def test_shorten_path_relative_to_cwd(tmp_path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    assert shorten_path(str(target), cwd=str(tmp_path)) == "src/app.py"


def test_summarize_content_heading_and_path():
    assert summarize_content("# Specify\n\nGoal") == "Specify"
    assert "dashboard_page.dart" in summarize_content(
        "Veja `lib/features/home/ui/dashboard_page.dart` para contexto"
    )


def test_extract_tool_target_from_diff_content():
    update = {
        "content": [
            {
                "type": "diff",
                "path": "/Users/me/proj/.pulse/specs/features/demo/spec.md",
            }
        ]
    }
    target = extract_tool_target(update, cwd="/Users/me/proj")
    assert target.endswith("spec.md")
    assert "features" in target


def test_extract_tool_target_from_search_output():
    assert extract_tool_target({"rawOutput": {"totalFiles": 4}}) == "4 files"
    assert ".pulse/specs/codebase" in extract_tool_target(
        {"rawOutput": {"error": "Path does not exist: /tmp/proj/.pulse/specs/codebase"}}
    )


def test_build_tool_labels_avoids_generic_duplication():
    kind, title, detail = build_tool_labels(
        {"title": "Read File", "kind": "read"},
    )
    assert kind == LogKind.READ
    assert title == "…"
    assert detail == "…"

    kind, title, detail = build_tool_labels(
        {
            "title": "Edit File",
            "kind": "edit",
            "content": [{"type": "diff", "path": "/repo/a/b/spec.md"}],
        },
        cwd="/repo",
    )
    assert kind == LogKind.EDIT
    assert title.endswith("spec.md")
