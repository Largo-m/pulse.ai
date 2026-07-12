from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pulse.tui.state import LogKind
from pulse.tui.tool_classify import classify_tool

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FRONTMATTER_NAME_RE = re.compile(r"(?m)^name:\s*[\"']?([^\"'\n]+)[\"']?")
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w.-]+)+(?:\.\w+)?"
    r"|(?:\.?[\w.-]+/)+[\w.-]+(?:\.\w+)?"
)
_BACKTICK_PATH_RE = re.compile(r"`([^`\n]+?/[^`\n]+)`")
_TITLE_PATH_RE = re.compile(
    r"(?:^|\s)((?:\.?/)?(?:[\w.-]+/)+[\w.-]+(?:\.\w+)?|(?:/[\w.-]+)+)"
)
_YAML_LINE_RE = re.compile(r"^[\w.-]+:(?:\s|$)")
_HTTP_LINE_RE = re.compile(r"^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\S+", re.I)
_OUTPUT_PATH_RE = re.compile(r"\*\*Output:\*\*\s*`([^`]+)`", re.IGNORECASE)
_INPUT_PATH_KEYS = (
    "path",
    "filePath",
    "file_path",
    "target",
    "targetFile",
    "target_file",
    "file",
    "uri",
    "filename",
)
_GENERIC_TITLES = frozenset(
    {
        "read",
        "read file",
        "reading",
        "write",
        "write file",
        "edit",
        "edit file",
        "find",
        "search",
        "grep",
        "rg",
        "glob",
        "list",
        "shell",
        "bash",
        "tool",
        "…",
        "...",
    }
)
_MAX_SEARCH_HITS = 3


def shorten_path(path: str, *, cwd: str | None = None) -> str:
    text = path.strip().strip("\"'`")
    if not text:
        return ""
    if text.startswith("file://"):
        text = text[7:]
    try:
        candidate = Path(text)
    except Exception:
        return text
    if cwd:
        try:
            return str(candidate.resolve().relative_to(Path(cwd).resolve()))
        except Exception:
            pass
    parts = candidate.parts
    if len(parts) > 4:
        return str(Path(*parts[-4:]))
    return text


def is_generic_title(title: str) -> bool:
    return title.strip().lower() in _GENERIC_TITLES


def _as_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _raw_input(update: dict[str, Any]) -> dict[str, Any]:
    return _as_dict(update.get("rawInput"))


def _raw_output(update: dict[str, Any]) -> dict[str, Any]:
    raw = update.get("rawOutput")
    as_dict = _as_dict(raw)
    if as_dict:
        return as_dict
    if isinstance(raw, str) and raw.strip():
        return {"content": raw}
    return {}


def _looks_like_path(value: str) -> bool:
    text = value.strip().strip("\"'`")
    if not text or "\n" in text:
        return False
    if text.startswith(("http://", "https://")):
        return False
    if "/" in text or text.startswith("."):
        return True
    return bool(re.search(r"\.\w{1,8}$", text))


def _is_low_quality_label(value: str) -> bool:
    text = value.strip()
    if not text or text in {"…", "..."}:
        return True
    if _YAML_LINE_RE.match(text):
        return True
    if _HTTP_LINE_RE.match(text):
        return True
    if is_generic_title(text):
        return True
    return False


def extract_paths(update: dict[str, Any], *, cwd: str | None = None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: object) -> None:
        if not isinstance(value, str) or not value.strip():
            return
        if not _looks_like_path(value) and "://" not in value:
            return
        short = shorten_path(value, cwd=cwd)
        if not short or short in seen or _is_low_quality_label(short):
            return
        seen.add(short)
        found.append(short)

    for key in ("path", "filePath", "uri"):
        add(update.get(key))

    locations = update.get("locations")
    if isinstance(locations, list):
        for item in locations:
            if isinstance(item, str):
                add(item)
            elif isinstance(item, dict):
                for nested in ("path", "filePath", "uri"):
                    add(item.get(nested))

    content = update.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            for nested in ("path", "filePath", "uri"):
                add(item.get(nested))

    raw_input = _raw_input(update)
    for key in _INPUT_PATH_KEYS:
        add(raw_input.get(key))

    title = str(update.get("title") or "").strip()
    if title:
        match = _TITLE_PATH_RE.search(title)
        if match:
            add(match.group(1))
        elif _looks_like_path(title):
            add(title)

    return found


def extract_tool_path(update: dict[str, Any], *, cwd: str | None = None) -> str:
    paths = extract_paths(update, cwd=cwd)
    return paths[0] if paths else ""


def extract_search_query(update: dict[str, Any]) -> str:
    raw_input = _raw_input(update)
    for key in ("pattern", "query", "regex", "text", "search", "needle", "glob", "glob_pattern"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip() and not is_generic_title(value):
            return value.strip()
    title = str(update.get("title") or "").strip()
    if title and not is_generic_title(title):
        lowered = title.lower()
        for prefix in (
            "search ",
            "searching ",
            "find ",
            "finding ",
            "grep ",
            "rg ",
            "searched for ",
            "search for ",
        ):
            if lowered.startswith(prefix):
                rest = title[len(prefix) :].strip(" :\"'")
                if rest and not is_generic_title(rest) and not _looks_like_path(rest):
                    return rest
                return ""
        if _looks_like_path(title):
            return ""
        return title
    return ""


def extract_search_scope(update: dict[str, Any], *, cwd: str | None = None) -> str:
    raw_input = _raw_input(update)
    for key in ("path", "filePath", "target", "cwd", "directory", "root"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            return shorten_path(value, cwd=cwd)
    query = extract_search_query(update)
    for key in ("glob", "glob_pattern"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != query:
            return value.strip()
    return ""


def extract_search_count(update: dict[str, Any]) -> int | None:
    raw_output = _raw_output(update)
    for key in ("totalFiles", "totalMatches", "count", "matches"):
        value = raw_output.get(key)
        if isinstance(value, int) and value >= 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    locations = update.get("locations")
    if isinstance(locations, list) and locations:
        return len(locations)
    return None


def format_search_labels(update: dict[str, Any], *, cwd: str | None = None) -> tuple[str, str]:
    query = extract_search_query(update)
    scope = extract_search_scope(update, cwd=cwd)
    count = extract_search_count(update)
    hits = extract_paths(update, cwd=cwd)
    if scope:
        hits = [path for path in hits if path != scope]

    if query:
        title = f"“{query}”" if not query.startswith(("*", "?")) else query
    elif count is not None:
        title = f"{count} file{'s' if count != 1 else ''}"
    else:
        title = "…"

    detail_lines: list[str] = []
    meta_parts: list[str] = []
    if scope:
        meta_parts.append(f"in {scope}")
    if count is not None:
        meta_parts.append(f"{count} file{'s' if count != 1 else ''}")
    if meta_parts:
        detail_lines.append("  ·  ".join(meta_parts) if len(meta_parts) > 1 else meta_parts[0])

    for path in hits[:_MAX_SEARCH_HITS]:
        detail_lines.append(path)
    remaining = len(hits) - _MAX_SEARCH_HITS
    if remaining > 0:
        detail_lines.append(f"(+{remaining})")

    return title, "\n".join(detail_lines)


def _content_texts(update: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    raw_output = _raw_output(update)
    content_text = raw_output.get("content")
    if isinstance(content_text, str) and content_text.strip():
        texts.append(content_text)
    elif isinstance(content_text, list):
        for item in content_text:
            if isinstance(item, str) and item.strip():
                texts.append(item)
            elif isinstance(item, dict):
                nested = item.get("text") or item.get("content")
                if isinstance(nested, str) and nested.strip():
                    texts.append(nested)

    content = update.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "content":
                nested = item.get("content")
                if isinstance(nested, dict):
                    text = nested.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
                elif isinstance(nested, str) and nested.strip():
                    texts.append(nested)
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return texts


def summarize_content(content: str, *, cwd: str | None = None) -> str:
    text = content.strip()
    if not text:
        return ""

    output_path = _OUTPUT_PATH_RE.search(text[:800])
    if output_path:
        return shorten_path(output_path.group(1), cwd=cwd)

    backtick = _BACKTICK_PATH_RE.search(text)
    if backtick:
        return shorten_path(backtick.group(1), cwd=cwd)

    path_match = _PATH_RE.search(text[:800])
    if path_match:
        return shorten_path(path_match.group(0), cwd=cwd)

    frontmatter = _FRONTMATTER_NAME_RE.search(text[:400])
    if frontmatter:
        return frontmatter.group(1).strip()

    heading = _HEADING_RE.search(text[:400])
    if heading:
        value = heading.group(1).strip()
        if not _is_low_quality_label(value):
            return value

    for line in text.splitlines()[:12]:
        candidate = line.strip()
        if not candidate or _is_low_quality_label(candidate):
            continue
        if len(candidate) > 80:
            return candidate[:77] + "…"
        return candidate
    return ""


def extract_tool_target(update: dict[str, Any], *, cwd: str | None = None) -> str:
    path = extract_tool_path(update, cwd=cwd)
    if path:
        return path

    raw_input = _raw_input(update)
    for key in ("glob", "pattern", "query", "command", "args"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return " ".join(str(part) for part in value)

    raw_output = _raw_output(update)
    if raw_output.get("error"):
        error = str(raw_output["error"])
        match = _PATH_RE.search(error)
        if match:
            return shorten_path(match.group(0), cwd=cwd)
        return error[:120]
    if "totalFiles" in raw_output:
        total = raw_output.get("totalFiles")
        return f"{total} file{'s' if total != 1 else ''}"

    for text in _content_texts(update):
        summary = summarize_content(text, cwd=cwd)
        if summary and not _is_low_quality_label(summary):
            return summary

    title = str(update.get("title") or update.get("toolName") or "").strip()
    if title and not is_generic_title(title):
        return title
    return ""


def merge_tool_update(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in update.items():
        if value is None:
            continue
        if key == "rawInput":
            incoming = _as_dict(value)
            if incoming:
                existing = _as_dict(merged.get("rawInput"))
                merged["rawInput"] = {**existing, **incoming} if existing else incoming
            elif isinstance(value, dict):
                merged["rawInput"] = dict(value)
            continue
        if key == "rawOutput":
            incoming = _as_dict(value)
            if incoming:
                existing = _as_dict(merged.get("rawOutput"))
                merged["rawOutput"] = {**existing, **incoming} if existing else incoming
            elif isinstance(value, str):
                merged["rawOutput"] = {"content": value}
            continue
        if key == "locations" and isinstance(value, list):
            if not value:
                continue
            existing = merged.get("locations")
            if isinstance(existing, list):
                merged["locations"] = [*existing, *value]
            else:
                merged["locations"] = list(value)
            continue
        if key == "content" and isinstance(value, list):
            if not value:
                continue
            existing = merged.get("content")
            if isinstance(existing, list):
                merged["content"] = [*existing, *value]
            else:
                merged["content"] = list(value)
            continue
        merged[key] = value
    return merged


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

    if log_kind == LogKind.SEARCH:
        search_title, search_detail = format_search_labels(update, cwd=cwd)
        return log_kind, search_title, search_detail

    path = extract_tool_path(update, cwd=cwd)
    if path:
        return log_kind, path, ""

    raw_output = _raw_output(update)
    if raw_output.get("error"):
        error = str(raw_output["error"])
        match = _PATH_RE.search(error)
        if match:
            return log_kind, shorten_path(match.group(0), cwd=cwd), ""
        return log_kind, error[:120], ""

    raw_input = _raw_input(update)
    for key in ("command", "args"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            return log_kind, value.strip(), ""
        if isinstance(value, list) and value:
            return log_kind, " ".join(str(part) for part in value), ""

    for text in _content_texts(update):
        summary = summarize_content(text, cwd=cwd)
        if summary and not _is_low_quality_label(summary):
            return log_kind, summary, ""

    if title and not is_generic_title(title):
        cleaned = title
        for prefix in ("Reading ", "Read ", "Editing ", "Edit ", "Writing ", "Write "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip(" :")
                break
        if cleaned and _looks_like_path(cleaned):
            return log_kind, shorten_path(cleaned, cwd=cwd), ""
        if cleaned and not _is_low_quality_label(cleaned):
            return log_kind, cleaned, ""
        if not _is_low_quality_label(title):
            return log_kind, title, ""

    return log_kind, "…", ""
