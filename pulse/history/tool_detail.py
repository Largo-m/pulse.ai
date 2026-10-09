from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from contextlib import suppress
from pathlib import Path

from pulse.domain.ports import JsonObject
from pulse.history.events import LogKind
from pulse.history.tool_classify import classify_tool

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FRONTMATTER_NAME_RE = re.compile(r"(?m)^name:\s*[\"']?([^\"'\n]+)[\"']?")
_PATH_RE = re.compile(
    r"(?:[A-Za-z]:)?(?:/[\w.-]+)+(?:\.\w+)?"
    r"|(?:\.?[\w.-]+/)+[\w.-]+(?:\.\w+)?"
)
_BACKTICK_PATH_RE = re.compile(r"`([^`\n]+?/[^`\n]+)`")
_TITLE_PATH_RE = re.compile(r"(?:^|\s)((?:\.?/)?(?:[\w.-]+/)+[\w.-]+(?:\.\w+)?|(?:/[\w.-]+)+)")
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
_GENERIC_GLOBS = frozenset({"*", "**", "**/*", "./**/*", "**/**"})
_PATH_FIELDS = ("path", "filePath", "uri")
_TARGET_INPUT_KEYS = ("glob", "pattern", "query", "command", "args")
_COMMAND_INPUT_KEYS = ("command", "args")
_VERB_PREFIXES = ("Reading ", "Read ", "Editing ", "Edit ", "Writing ", "Write ")
# (pattern, prefix it searches, group): an explicit output marker beats a quoted
# path, which beats any path-looking token.
_TEXT_PATH_PATTERNS: tuple[tuple[re.Pattern[str], int | None, int], ...] = (
    (_OUTPUT_PATH_RE, 800, 1),
    (_BACKTICK_PATH_RE, None, 1),
    (_PATH_RE, 800, 0),
)


def shorten_path(path: str, *, cwd: str | None = None) -> str:
    """Path as the artifacts tab opens it: relative to the workspace.

    The runtime reports the same file as absolute (`locations`) and relative
    (`rawInput`); both must map to the same string or the artifact is duplicated.
    Relative paths are returned as-is because `resolve()` would anchor them to
    the daemon's cwd, not the workspace.
    """
    text = path.strip().strip("\"'`")
    if not text:
        return ""
    if text.startswith("file://"):
        text = text[7:]
    candidate = Path(text)
    if not candidate.is_absolute():
        return text.removeprefix("./") or text
    if cwd:
        # Outside the workspace (ValueError), unreadable or with a NUL byte
        # (OSError / ValueError), or a symlink loop (RuntimeError before 3.13):
        # the path is still shown, shortened below.
        with suppress(ValueError, OSError, RuntimeError):
            return str(candidate.resolve().relative_to(Path(cwd).resolve()))
    parts = candidate.parts
    if len(parts) > 4:
        return str(Path(*parts[-4:]))
    return text


def is_generic_title(title: str) -> bool:
    return title.strip().lower() in _GENERIC_TITLES


def _as_dict(value: object) -> JsonObject:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _raw_input(update: JsonObject) -> JsonObject:
    return _as_dict(update.get("rawInput"))


def _raw_output(update: JsonObject) -> JsonObject:
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


def _list_items(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _nested_paths(item: JsonObject) -> Iterator[object]:
    return (item.get(key) for key in _PATH_FIELDS)


def _location_candidates(locations: object) -> Iterator[object]:
    """A location is either the path itself or an object holding it."""
    for item in _list_items(locations):
        if isinstance(item, dict):
            yield from _nested_paths(item)
        else:
            yield item


def _content_candidates(content: object) -> Iterator[object]:
    for item in _list_items(content):
        if isinstance(item, dict):
            yield from _nested_paths(item)


def _title_path(update: JsonObject) -> str:
    title = str(update.get("title") or "").strip()
    match = _TITLE_PATH_RE.search(title)
    if match:
        return match.group(1)
    return title if _looks_like_path(title) else ""


def _path_candidates(update: JsonObject) -> Iterator[object]:
    """Every field a runtime may put a path in, most explicit first."""
    yield from _nested_paths(update)
    yield from _location_candidates(update.get("locations"))
    yield from _content_candidates(update.get("content"))
    raw_input = _raw_input(update)
    yield from (raw_input.get(key) for key in _INPUT_PATH_KEYS)
    yield _title_path(update)


def _path_label(value: object, *, cwd: str | None) -> str:
    """The path as shown, or empty when the value is not a usable path."""
    if not isinstance(value, str) or not value.strip():
        return ""
    if not _looks_like_path(value) and "://" not in value:
        return ""
    short = shorten_path(value, cwd=cwd)
    return "" if _is_low_quality_label(short) else short


def extract_paths(update: JsonObject, *, cwd: str | None = None) -> list[str]:
    labels = (_path_label(value, cwd=cwd) for value in _path_candidates(update))
    return list(dict.fromkeys(label for label in labels if label))


def extract_tool_path(update: JsonObject, *, cwd: str | None = None) -> str:
    paths = extract_paths(update, cwd=cwd)
    return paths[0] if paths else ""


def extract_search_query(update: JsonObject) -> str:
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


def extract_search_scope(update: JsonObject, *, cwd: str | None = None) -> str:
    raw_input = _raw_input(update)
    for key in ("path", "filePath", "target", "target_directory", "cwd", "directory", "root"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            return shorten_path(value, cwd=cwd)
    query = extract_search_query(update)
    for key in ("glob", "glob_pattern"):
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != query:
            return value.strip()
    return ""


def extract_search_count(update: JsonObject) -> int | None:
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


def _file_count(count: object) -> str:
    return f"{count} file{'s' if count != 1 else ''}"


def _search_headline(query: str, scope: str, count: int | None) -> tuple[str, list[str]]:
    """The search title and the facts it leaves for the detail line."""
    if query and query in _GENERIC_GLOBS and scope:
        return scope, [query]
    if query:
        title = query if query.startswith(("*", "?")) else f"“{query}”"
        return title, [f"in {scope}"] if scope else []
    if scope:
        return scope, []
    if count is not None:
        return _file_count(count), []
    return "…", []


def format_search_labels(update: JsonObject, *, cwd: str | None = None) -> tuple[str, str]:
    query = extract_search_query(update)
    scope = extract_search_scope(update, cwd=cwd)
    count = extract_search_count(update)
    hits = [path for path in extract_paths(update, cwd=cwd) if path != scope]

    title, meta_parts = _search_headline(query, scope, count)
    if count is not None:
        meta_parts.append(_file_count(count))
    detail_lines = ["  ·  ".join(meta_parts)] if meta_parts else []
    detail_lines.extend(hits[:_MAX_SEARCH_HITS])
    remaining = len(hits) - _MAX_SEARCH_HITS
    if remaining > 0:
        detail_lines.append(f"(+{remaining})")
    return title, "\n".join(detail_lines)


def _nonblank(value: object) -> list[str]:
    return [value] if isinstance(value, str) and value.strip() else []


def _raw_output_texts(update: JsonObject) -> list[str]:
    content = _raw_output(update).get("content")
    if not isinstance(content, list):
        return _nonblank(content)
    texts: list[str] = []
    for item in content:
        nested = (item.get("text") or item.get("content")) if isinstance(item, dict) else item
        texts.extend(_nonblank(nested))
    return texts


def _block_texts(block: JsonObject) -> list[str]:
    """Text of an ACP content block: a `content` wrapper and/or a plain `text` field."""
    texts: list[str] = []
    if block.get("type") == "content":
        nested = block.get("content")
        texts.extend(_nonblank(nested.get("text") if isinstance(nested, dict) else nested))
    texts.extend(_nonblank(block.get("text")))
    return texts


def _content_texts(update: JsonObject) -> list[str]:
    texts = _raw_output_texts(update)
    for block in _list_items(update.get("content")):
        if isinstance(block, dict):
            texts.extend(_block_texts(block))
    return texts


def _path_in_text(text: str, *, cwd: str | None) -> str | None:
    """The first path the text names, by pattern priority; `None` when it names none."""
    for pattern, window, group in _TEXT_PATH_PATTERNS:
        match = pattern.search(text[:window])
        if match:
            return shorten_path(match.group(group), cwd=cwd)
    return None


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines()[:12]:
        candidate = line.strip()
        if not candidate or _is_low_quality_label(candidate):
            continue
        if len(candidate) > 80:
            return candidate[:77] + "…"
        return candidate
    return ""


def _label_in_text(text: str) -> str:
    frontmatter = _FRONTMATTER_NAME_RE.search(text[:400])
    if frontmatter:
        return frontmatter.group(1).strip()
    heading = _HEADING_RE.search(text[:400])
    if heading:
        value = heading.group(1).strip()
        if not _is_low_quality_label(value):
            return value
    return _first_meaningful_line(text)


def summarize_content(content: str, *, cwd: str | None = None) -> str:
    text = content.strip()
    if not text:
        return ""
    path = _path_in_text(text, cwd=cwd)
    if path is not None:
        return path
    return _label_in_text(text)


def _input_value(raw_input: JsonObject, keys: tuple[str, ...]) -> str | None:
    """The first of `keys` the tool was called with; `None` when none was given."""
    for key in keys:
        value = raw_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            return " ".join(str(part) for part in value)
    return None


def _error_label(raw_output: JsonObject, *, cwd: str | None) -> str | None:
    """The path an error names, else the error itself; `None` when the tool did not fail."""
    error = raw_output.get("error")
    if not error:
        return None
    text = str(error)
    match = _PATH_RE.search(text)
    if match:
        return shorten_path(match.group(0), cwd=cwd)
    return text[:120]


def _content_summary(update: JsonObject, *, cwd: str | None) -> str:
    for text in _content_texts(update):
        summary = summarize_content(text, cwd=cwd)
        if summary and not _is_low_quality_label(summary):
            return summary
    return ""


def extract_tool_target(update: JsonObject, *, cwd: str | None = None) -> str:
    path = extract_tool_path(update, cwd=cwd)
    if path:
        return path
    target = _input_value(_raw_input(update), _TARGET_INPUT_KEYS)
    if target is not None:
        return target
    raw_output = _raw_output(update)
    error = _error_label(raw_output, cwd=cwd)
    if error is not None:
        return error
    if "totalFiles" in raw_output:
        return _file_count(raw_output.get("totalFiles"))
    summary = _content_summary(update, cwd=cwd)
    if summary:
        return summary
    title = str(update.get("title") or update.get("toolName") or "").strip()
    return "" if is_generic_title(title) else title


Merger = Callable[[object, object], object | None]
"""Combines a field already known with its streamed update; `None` keeps the known value."""


def _merge_objects(current: object, incoming: object) -> object | None:
    """Merge key by key: a truncated or partial update must not erase what was known."""
    update = _as_dict(incoming)
    if not update:
        return None
    existing = _as_dict(current)
    return {**existing, **update} if existing else update


def _merge_raw_output(current: object, incoming: object) -> object | None:
    merged = _merge_objects(current, incoming)
    if merged is None and isinstance(incoming, str):
        return {"content": incoming}
    return merged


def _append_items(current: object, incoming: object) -> object | None:
    """Lists accumulate across updates; anything else simply replaces the field."""
    if not isinstance(incoming, list):
        return incoming
    if not incoming:
        return None
    return [*current, *incoming] if isinstance(current, list) else list(incoming)


def _replace(_current: object, incoming: object) -> object | None:
    return incoming


_MERGERS: dict[str, Merger] = {
    "rawInput": _merge_objects,
    "rawOutput": _merge_raw_output,
    "locations": _append_items,
    "content": _append_items,
}


def merge_tool_update(base: JsonObject, update: JsonObject) -> JsonObject:
    merged = dict(base)
    for key, value in update.items():
        if value is None:
            continue
        combined = _MERGERS.get(key, _replace)(merged.get(key), value)
        if combined is not None:
            merged[key] = combined
    return merged


def _strip_verb(title: str) -> str:
    for prefix in _VERB_PREFIXES:
        if title.startswith(prefix):
            return title[len(prefix) :].strip(" :")
    return title


def _title_label(title: str, *, cwd: str | None) -> str:
    """The tool title without its verb, the last resort before the placeholder."""
    if not title or is_generic_title(title):
        return "…"
    cleaned = _strip_verb(title)
    if cleaned and _looks_like_path(cleaned):
        return shorten_path(cleaned, cwd=cwd)
    if cleaned and not _is_low_quality_label(cleaned):
        return cleaned
    if not _is_low_quality_label(title):
        return title
    return "…"


def _tool_label(update: JsonObject, title: str, *, cwd: str | None) -> str:
    """Most specific first: the file, the error, the command, the output, the title."""
    path = extract_tool_path(update, cwd=cwd)
    if path:
        return path
    error = _error_label(_raw_output(update), cwd=cwd)
    if error is not None:
        return error
    command = _input_value(_raw_input(update), _COMMAND_INPUT_KEYS)
    if command is not None:
        return command
    return _content_summary(update, cwd=cwd) or _title_label(title, cwd=cwd)


def build_tool_labels(
    update: JsonObject,
    *,
    cwd: str | None = None,
    fallback_kind: LogKind | None = None,
) -> tuple[LogKind, str, str]:
    title = str(update.get("title") or update.get("toolName") or "").strip()
    log_kind = fallback_kind or classify_tool(
        title,
        kind=str(update.get("kind") or ""),
        tool_name=str(update.get("toolName") or ""),
    )
    if log_kind == LogKind.SEARCH:
        search_title, search_detail = format_search_labels(update, cwd=cwd)
        return log_kind, search_title, search_detail
    return log_kind, _tool_label(update, title, cwd=cwd), ""
