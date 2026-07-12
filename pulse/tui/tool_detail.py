from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pulse.tui.state import LogKind
from pulse.tui.tool_classify import classify_tool

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FRONTMATTER_NAME_RE = re.compile(r"(?m)^name:\s*[\"']?([^\"'\n]+)[\"']?")
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w.-]+)+(?:\.\w+)?|(?:[\w.-]+/)+[\w.-]+\.\w+"
)
_BACKTICK_PATH_RE = re.compile(r"`([^`\n]+?/[^`\n]+)`")
_GENERIC_TITLES = frozenset(
    {
        "read",
        "read file",
        "write",
        "write file",
        "edit",
        "edit file",
        "find",
        "search",
        "list",
        "shell",
        "bash",
        "tool",
    }
)


def shorten_path(path: str, *, cwd: str | None = None) -> str:
    text = path.strip()
    if not text:
        return ""
    try:
        candidate = Path(text)
        if cwd:
            try:
                return str(candidate.resolve().relative_to(Path(cwd).resolve()))
            except Exception:
                pass
        parts = candidate.parts
        if len(parts) > 4:
            return str(Path(*parts[-4:]))
        return text
    except Exception:
        return text


def is_generic_title(title: str) -> bool:
    return title.strip().lower() in _GENERIC_TITLES


def extract_tool_target(update: dict[str, Any], *, cwd: str | None = None) -> str:
    for key in ("path", "filePath", "uri"):
        value = update.get(key)
        if isinstance(value, str) and value.strip():
            return shorten_path(value, cwd=cwd)

    locations = update.get("locations")
    if isinstance(locations, list):
        for item in locations:
            if isinstance(item, str) and item.strip():
                return shorten_path(item, cwd=cwd)
            if isinstance(item, dict):
                for nested in ("path", "filePath", "uri"):
                    if item.get(nested):
                        return shorten_path(str(item[nested]), cwd=cwd)

    content = update.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            for nested in ("path", "filePath", "uri"):
                if item.get(nested):
                    return shorten_path(str(item[nested]), cwd=cwd)

    raw_input = update.get("rawInput")
    if isinstance(raw_input, dict):
        for key in ("path", "filePath", "target", "glob", "pattern", "query", "command", "args"):
            value = raw_input.get(key)
            if isinstance(value, str) and value.strip():
                if key in {"path", "filePath", "target", "glob"}:
                    return shorten_path(value, cwd=cwd)
                return value.strip()
            if isinstance(value, list) and value:
                return " ".join(str(part) for part in value)

    raw_output = update.get("rawOutput")
    if isinstance(raw_output, dict):
        if raw_output.get("error"):
            error = str(raw_output["error"])
            match = _PATH_RE.search(error)
            if match:
                return shorten_path(match.group(0), cwd=cwd)
            return error[:120]
        if "totalFiles" in raw_output:
            total = raw_output.get("totalFiles")
            return f"{total} file{'s' if total != 1 else ''}"
        content_text = raw_output.get("content")
        if isinstance(content_text, str) and content_text.strip():
            return summarize_content(content_text, cwd=cwd)

    title = str(update.get("title") or update.get("toolName") or "").strip()
    if title and not is_generic_title(title):
        return title
    return ""


def summarize_content(content: str, *, cwd: str | None = None) -> str:
    text = content.strip()
    if not text:
        return ""

    backtick = _BACKTICK_PATH_RE.search(text)
    if backtick:
        return shorten_path(backtick.group(1), cwd=cwd)

    path_match = _PATH_RE.search(text[:400])
    if path_match and ("/" in path_match.group(0) or "." in path_match.group(0)):
        return shorten_path(path_match.group(0), cwd=cwd)

    frontmatter = _FRONTMATTER_NAME_RE.search(text[:400])
    if frontmatter:
        return frontmatter.group(1).strip()

    heading = _HEADING_RE.search(text[:400])
    if heading:
        return heading.group(1).strip()

    first = text.splitlines()[0].strip()
    if len(first) > 80:
        return first[:77] + "…"
    return first


def build_tool_labels(
    update: dict[str, Any],
    *,
    cwd: str | None = None,
    fallback_kind: LogKind | None = None,
) -> tuple[LogKind, str, str]:
    title = str(update.get("title") or update.get("toolName") or "").strip()
    tool_kind = str(update.get("kind") or "")
    log_kind = fallback_kind or classify_tool(
        title,
        kind=tool_kind,
        tool_name=str(update.get("toolName") or ""),
    )
    target = extract_tool_target(update, cwd=cwd)
    if not target:
        if title and not is_generic_title(title):
            target = title
        else:
            target = "…"
    kind_label = log_kind.value
    return log_kind, target, target
