from __future__ import annotations

import re

from pulse.history.events import LogKind

_SEARCH = re.compile(r"\b(search|grep|find|glob|rg)\b", re.IGNORECASE)
_LIST = re.compile(r"\b(list|ls|dir|glob)\b", re.IGNORECASE)
_READ = re.compile(r"\b(read|cat|open|view|get)\b", re.IGNORECASE)
_EDIT = re.compile(r"\b(edit|patch|strreplace|replace|apply)\b", re.IGNORECASE)
_WRITE = re.compile(r"\b(write|create|save|mkdir)\b", re.IGNORECASE)
_SHELL = re.compile(r"\b(shell|bash|terminal|command|exec)\b", re.IGNORECASE)


def classify_tool(title: str | None = None, *, kind: str | None = None, tool_name: str | None = None) -> LogKind:
    haystack = " ".join(part for part in (kind, tool_name, title) if part).strip()
    if not haystack:
        return LogKind.TOOL
    if _SEARCH.search(haystack):
        return LogKind.SEARCH
    if _EDIT.search(haystack):
        return LogKind.EDIT
    if _WRITE.search(haystack):
        return LogKind.WRITE
    if _SHELL.search(haystack):
        return LogKind.SHELL
    if _READ.search(haystack):
        return LogKind.READ
    if _LIST.search(haystack):
        return LogKind.LIST
    return LogKind.TOOL


def extract_tool_path(title: str) -> str:
    text = title.strip()
    if not text:
        return ""
    for sep in (": ", " — ", " - ", " → ", "->"):
        if sep in text:
            return text.split(sep, 1)[-1].strip()
    parts = text.split()
    if len(parts) >= 2 and ("/" in parts[-1] or parts[-1].endswith((".py", ".ts", ".md", ".yaml", ".yml", ".json"))):
        return parts[-1]
    return text
