from __future__ import annotations

from pulse.history.tool_detail import (
    build_tool_labels,
    extract_paths,
    extract_tool_target,
    format_search_labels,
    merge_tool_update,
    shorten_path,
    summarize_content,
)
from pulse.tui.state import LogKind


def test_shorten_path_relative_to_cwd(tmp_path):
    target = tmp_path / "src" / "app.py"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    assert shorten_path(str(target), cwd=str(tmp_path)) == "src/app.py"


def test_same_file_in_both_spellings_maps_to_same_key(tmp_path):
    """The runtime reports absolute paths in `locations` and relative ones in `rawInput`.

    Two keys for one file produced duplicate artifact tabs, and the second one
    (truncated to 4 segments) opened nothing.
    """
    target = tmp_path / ".pulse" / "specs" / "features" / "barra" / "PRD.md"
    target.parent.mkdir(parents=True)
    target.write_text("x")
    relative = ".pulse/specs/features/barra/PRD.md"

    assert shorten_path(str(target), cwd=str(tmp_path)) == relative
    assert shorten_path(relative, cwd=str(tmp_path)) == relative
    assert shorten_path("./" + relative, cwd=str(tmp_path)) == relative


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


def test_merge_tool_update_keeps_the_last_good_raw_input_over_truncated_json():
    """A streamed `rawInput` cut mid-JSON must not erase what was already known."""
    merged = merge_tool_update(
        {"rawInput": {"path": "/repo/a.md"}},
        {"rawInput": '{"path": "/repo/b.md", "pat'},
    )
    assert merged["rawInput"] == {"path": "/repo/a.md"}


def test_shorten_path_outside_the_workspace_keeps_the_last_four_parts(tmp_path):
    """A file the agent touched elsewhere is still shown, just shortened."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    outside = "/opt/data/very/deep/tree/file.md"

    assert shorten_path(outside, cwd=str(workspace)) == "very/deep/tree/file.md"


def test_shorten_path_with_a_nul_byte_is_returned_as_given(tmp_path):
    """An agent path that the OS refuses to resolve must not break the labels."""
    assert shorten_path("/repo/a\x00b", cwd=str(tmp_path)) == "/repo/a\x00b"


def test_shorten_path_through_a_symlink_loop_still_yields_a_path(tmp_path):
    """A symlink loop raises on some Python versions; the path is still shown."""
    (tmp_path / "a").symlink_to(tmp_path / "b")
    (tmp_path / "b").symlink_to(tmp_path / "a")

    shown = shorten_path(str(tmp_path / "a" / "x.md"), cwd=str(tmp_path))

    assert shown.endswith("x.md")


def test_extract_paths_lists_each_file_once_most_explicit_field_first(tmp_path):
    """The artifacts tab keys on these strings: one file must never yield two entries."""
    update = {
        "path": str(tmp_path / "a.md"),
        "locations": ["b.md", {"path": str(tmp_path / "a.md")}, 7],
        "content": ["c.md", {"type": "diff", "path": "d.md"}],
        "rawInput": {"file_path": "./b.md", "filename": "e.md"},
        "title": "Edit f/g.md",
    }

    assert extract_paths(update, cwd=str(tmp_path)) == ["a.md", "b.md", "d.md", "e.md", "f/g.md"]


def test_extract_paths_ignores_labels_that_are_not_paths():
    update = {"path": "phases:", "title": "Read File", "locations": ["plain", 3]}

    assert extract_paths(update) == []


def test_format_search_labels_without_query_or_scope_titles_the_count():
    assert format_search_labels({"rawOutput": {"totalFiles": 1}}) == ("1 file", "1 file")
    assert format_search_labels({}) == ("…", "")


def test_format_search_labels_wildcard_query_is_shown_unquoted_with_its_scope():
    title, detail = format_search_labels(
        {"rawInput": {"pattern": "*.py", "path": "src"}, "rawOutput": {"count": "3"}}
    )

    assert title == "*.py"
    assert detail == "in src  ·  3 files"


def test_summarize_content_prefers_the_output_marker_over_other_paths():
    text = "See `lib/other.dart`\n**Output:** `out/report.md`"

    assert summarize_content(text) == "out/report.md"


def test_summarize_content_names_frontmatter_else_the_first_meaningful_line():
    assert summarize_content("---\nname: 'reviewer'\n---") == "reviewer"
    assert summarize_content("phases:\n\nThe useful line") == "The useful line"
    long_line = "word " * 30

    assert summarize_content(long_line) == long_line.strip()[:77] + "…"
    assert summarize_content("   ") == ""
    assert summarize_content("key: value\n…") == ""


def test_extract_tool_target_falls_back_through_input_output_and_title():
    assert extract_tool_target({"rawInput": {"args": ["git", "status"]}}) == "git status"
    assert extract_tool_target({"rawInput": {"command": "  ", "query": "needle"}}) == "needle"
    assert extract_tool_target({"rawOutput": {"error": "boom"}}) == "boom"
    assert extract_tool_target({"rawOutput": {"totalFiles": 1}}) == "1 file"
    assert extract_tool_target({"rawOutput": "# Notes\nbody"}) == "Notes"
    assert extract_tool_target({"toolName": "Deploy"}) == "Deploy"
    assert extract_tool_target({"title": "Read File"}) == ""


def test_build_tool_labels_uses_the_error_then_the_command():
    _, from_error, _ = build_tool_labels(
        {"kind": "execute", "rawOutput": {"error": "no such file: /repo/x/y.md"}}, cwd="/repo"
    )
    _, from_command, _ = build_tool_labels(
        {"kind": "execute", "rawInput": {"command": " npm test "}}
    )

    assert from_error == "x/y.md"
    assert from_command == "npm test"


def test_build_tool_labels_reads_text_from_raw_output_lists():
    _, title, _ = build_tool_labels(
        {"kind": "read", "rawOutput": {"content": [" ", {"text": "# Spec"}, {"content": "x"}]}}
    )

    assert title == "Spec"


def test_build_tool_labels_strips_the_verb_from_a_free_text_title():
    _, title, _ = build_tool_labels({"kind": "execute", "title": "Editing : release notes"})
    _, yaml_like, _ = build_tool_labels({"kind": "execute", "title": "phases:"})

    assert title == "release notes"
    assert yaml_like == "…"


def test_merge_tool_update_accumulates_lists_and_replaces_scalars():
    """Streamed updates add locations and content; a missing field never erases one."""
    merged = merge_tool_update(
        {"locations": ["a.md"], "content": [{"text": "1"}], "title": "old", "kind": "read"},
        {
            "locations": ["b.md"],
            "content": [],
            "title": "new",
            "kind": None,
            "rawOutput": "plain output",
        },
    )

    assert merged == {
        "locations": ["a.md", "b.md"],
        "content": [{"text": "1"}],
        "title": "new",
        "kind": "read",
        "rawOutput": {"content": "plain output"},
    }


def test_merge_tool_update_replaces_a_list_field_sent_as_another_shape():
    merged = merge_tool_update({"locations": ["a.md"]}, {"locations": "b.md", "content": ["x"]})

    assert merged == {"locations": "b.md", "content": ["x"]}


def test_merge_tool_update_merges_raw_output_key_by_key():
    merged = merge_tool_update(
        {"rawOutput": {"totalFiles": 2}}, {"rawOutput": '{"content": "done"}'}
    )

    assert merged["rawOutput"] == {"totalFiles": 2, "content": "done"}
