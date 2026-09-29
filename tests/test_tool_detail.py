from __future__ import annotations

from pulse.tui.state import LogKind
from pulse.tui.tool_detail import (
    build_tool_labels,
    extract_tool_target,
    format_search_labels,
    merge_tool_update,
    shorten_path,
    summarize_content,
)


def test_shorten_path_relative_to_cwd(tmp_path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    assert shorten_path(str(target), cwd=str(tmp_path)) == "src/app.py"


def test_summarize_content_heading_and_path():
    assert summarize_content("# PRD\n\nGoal") == "PRD"
    assert "dashboard_page.dart" in summarize_content(
        "Veja `lib/features/home/ui/dashboard_page.dart` para contexto"
    )


def test_extract_tool_target_from_diff_content():
    update = {
        "content": [
            {
                "type": "diff",
                "path": "/Users/me/proj/docs/PRD.md",
            }
        ]
    }
    target = extract_tool_target(update, cwd="/Users/me/proj")
    assert target.endswith("PRD.md")
    assert "docs" in target


def test_extract_tool_target_from_search_output():
    assert extract_tool_target({"rawOutput": {"totalFiles": 4}}) == "4 files"
    assert "docs/codebase" in extract_tool_target(
        {"rawOutput": {"error": "Path does not exist: /tmp/proj/docs/codebase"}}
    )


def test_build_tool_labels_avoids_generic_duplication():
    kind, title, detail = build_tool_labels(
        {"title": "Read File", "kind": "read"},
    )
    assert kind == LogKind.READ
    assert title == "…"
    assert detail == ""

    kind, title, detail = build_tool_labels(
        {
            "title": "Edit File",
            "kind": "edit",
            "content": [{"type": "diff", "path": "/repo/a/b/PRD.md"}],
        },
        cwd="/repo",
    )
    assert kind == LogKind.EDIT
    assert title.endswith("PRD.md")
    assert detail == ""


def test_build_tool_labels_rejects_yaml_key_only():
    kind, title, detail = build_tool_labels(
        {
            "title": "Read File",
            "kind": "read",
            "rawOutput": {"content": "phases:\n  - prd\n"},
        }
    )
    assert kind == LogKind.READ
    assert title != "phases:"
    assert title == "…" or "prd" in title.lower() or title.startswith("-")


def test_build_tool_labels_read_prefers_path():
    kind, title, detail = build_tool_labels(
        {
            "title": "Read File",
            "kind": "read",
            "rawInput": {"path": "/repo/vendor/config.yaml"},
            "rawOutput": {"content": "version: 1\n"},
        },
        cwd="/repo",
    )
    assert kind == LogKind.READ
    assert title.endswith("config.yaml")
    assert "version" not in title
    assert detail == ""


def test_build_tool_labels_read_from_title_path():
    kind, title, detail = build_tool_labels(
        {
            "title": "Reading docs/STATE.md",
            "kind": "read",
        }
    )
    assert kind == LogKind.READ
    assert title.endswith("STATE.md")
    assert detail == ""


def test_build_tool_labels_read_from_locations():
    kind, title, detail = build_tool_labels(
        {
            "title": "Read File",
            "kind": "read",
            "locations": [{"path": "/repo/docs/PRD.md"}],
        },
        cwd="/repo",
    )
    assert kind == LogKind.READ
    assert title.endswith("PRD.md")


def test_build_tool_labels_read_from_nested_content_text():
    kind, title, detail = build_tool_labels(
        {
            "title": "Read File",
            "kind": "read",
            "content": [
                {
                    "type": "content",
                    "content": {
                        "type": "text",
                        "text": "# PRD\n\nGoal",
                    },
                }
            ],
        }
    )
    assert kind == LogKind.READ
    assert title == "PRD"


def test_format_search_labels_with_hits():
    title, detail = format_search_labels(
        {
            "kind": "search",
            "rawInput": {"pattern": "dashboard", "path": "/repo/docs"},
            "rawOutput": {"totalFiles": 4},
            "locations": [
                "/repo/docs/PRD.md",
                "/repo/vendor/PRD.md",
                "/repo/vendor/config.yaml",
                "/repo/docs/STATE.md",
            ],
        },
        cwd="/repo",
    )
    assert title == "“dashboard”"
    assert "in docs" in detail
    assert "4 files" in detail
    assert "PRD.md" in detail
    assert "(+1)" in detail


def test_format_search_labels_target_directory_and_generic_glob():
    title, detail = format_search_labels(
        {
            "kind": "search",
            "rawInput": {
                "glob_pattern": "**/*",
                "target_directory": "/repo/docs/features/demo",
            },
            "rawOutput": {"totalFiles": 1},
        },
        cwd="/repo",
    )
    assert "features/demo" in title or title.endswith("demo")
    assert "**/*" in detail
    assert "1 file" in detail


def test_format_search_labels_grep_pattern():
    title, detail = format_search_labels(
        {
            "kind": "search",
            "rawInput": {
                "pattern": "home|Home|dashboard",
                "path": "/repo/lib",
                "glob": "**/*.{dart,md}",
            },
            "rawOutput": {"totalFiles": 80},
        },
        cwd="/repo",
    )
    assert "home|Home|dashboard" in title
    assert "in lib" in detail
    assert "80 files" in detail


def test_format_search_labels_glob():
    title, detail = format_search_labels(
        {
            "kind": "search",
            "rawInput": {"glob": "**/*dashboard*"},
            "rawOutput": {"totalFiles": 2},
            "locations": [
                "/repo/lib/features/home/ui/dashboard_page.dart",
                "/repo/lib/features/home/ui/dashboard_card.dart",
            ],
        },
        cwd="/repo",
    )
    assert title == "**/*dashboard*"
    assert "2 files" in detail
    assert "dashboard_page.dart" in detail


def test_merge_tool_update_keeps_raw_input():
    merged = merge_tool_update(
        {"rawInput": {"pattern": "dashboard", "path": ".pulse"}, "kind": "search"},
        {"rawOutput": {"totalFiles": 4}, "locations": ["a.md"]},
    )
    assert merged["rawInput"]["pattern"] == "dashboard"
    assert merged["rawOutput"]["totalFiles"] == 4
    assert merged["locations"] == ["a.md"]


def test_merge_tool_update_parses_json_raw_input():
    merged = merge_tool_update(
        {},
        {"rawInput": '{"path": "/repo/a.md", "pattern": "x"}'},
    )
    assert merged["rawInput"]["path"] == "/repo/a.md"
