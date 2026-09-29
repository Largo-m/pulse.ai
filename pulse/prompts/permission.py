from __future__ import annotations

from typing import Any, Literal

PermissionPolicy = Literal["ask", "auto_approve", "deny_writes"]

_PATH_KEYS = frozenset({"path", "filepath", "file_path", "uri", "absolute_path"})


def permission_selected(option_id: str) -> dict[str, Any]:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def permission_cancelled() -> dict[str, Any]:
    return {"outcome": {"outcome": "cancelled"}}


def pick_permission_option(options: list[Any], *, prefer: str) -> str | None:
    for option in options:
        if not isinstance(option, dict):
            continue
        kind = str(option.get("kind", ""))
        option_id = str(option.get("optionId", ""))
        if not option_id:
            continue
        if prefer == "allow" and kind.startswith("allow"):
            return option_id
        if prefer == "reject" and kind.startswith("reject"):
            return option_id
    return None


def permission_target_paths(params: dict[str, Any]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text or text in seen:
            return
        seen.add(text)
        found.append(text)

    def walk(node: Any, *, depth: int = 0) -> None:
        if depth > 6 or node is None:
            return
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).lower() in _PATH_KEYS:
                    add(value)
                walk(value, depth=depth + 1)
            return
        if isinstance(node, list):
            for item in node:
                walk(item, depth=depth + 1)

    walk(params)
    permission = params.get("permission")
    if isinstance(permission, dict):
        add(permission.get("title"))
    return found


