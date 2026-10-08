from __future__ import annotations

from typing import Any, Literal

from pulse.domain import ui_text
from pulse.replies.ask_question import format_option_label

PermissionPolicy = Literal["ask", "auto_approve", "deny_writes"]

_POLICIES: dict[str, PermissionPolicy] = {
    "ask": "ask",
    "auto_approve": "auto_approve",
    "deny_writes": "deny_writes",
}


def parse_policy(value: str) -> PermissionPolicy:
    """The policy a config value names; anything else asks, since asking is never unsafe."""
    return _POLICIES.get(value.strip(), "ask")


_PATH_KEYS = frozenset({"path", "filepath", "file_path", "uri", "absolute_path"})

_READ_ONLY_KINDS = frozenset({"read", "search", "fetch", "think"})
_WRITE_KINDS = frozenset({"edit", "delete", "move"})


def _permission_choice_label(option: dict[str, Any]) -> str:
    name = str(option.get("name") or option.get("label") or "").strip()
    if name:
        return name
    kind = str(option.get("kind", "")).lower().replace("-", "_")
    return ui_text.PERMISSION_KIND_LABELS.get(
        kind, kind.replace("_", " ").strip() or ui_text.OPTION_FALLBACK
    )


def build_permission_choices(options: list[Any]) -> list[tuple[str, str]]:
    """Permission request options, lettered as the dock shows them."""
    choices: list[tuple[str, str]] = []
    index = 0
    for option in options:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("optionId") or option.get("id") or "")
        if not option_id:
            continue
        label = format_option_label(index, _permission_choice_label(option))
        choices.append((option_id, label))
        index += 1
    if not choices:
        return [
            ("allow-once", format_option_label(0, ui_text.ALLOW_ONCE)),
            ("reject-once", format_option_label(1, ui_text.REJECT_ONCE)),
        ]
    return choices


def permission_prompt_text(permission: dict[str, Any], tool_call: dict[str, Any]) -> str:
    title = str(permission.get("title") or "").strip()
    description = str(permission.get("description") or "").strip()
    tool_title = str(tool_call.get("title") or "").strip()
    parts: list[str] = []
    for part in (title, description, tool_title):
        if part and part not in parts:
            parts.append(part)
    if not parts:
        return ui_text.PERMISSION_PROMPT_FALLBACK
    return "\n".join(parts)


def permission_selected(option_id: str) -> dict[str, Any]:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def permission_cancelled() -> dict[str, Any]:
    return {"outcome": {"outcome": "cancelled"}}


def pick_permission_option(options: list[Any], *, prefer: str) -> str | None:
    """First option matching `prefer`, with `*_once` ahead of `*_always`.

    `allow_always` makes the agent remember the choice (ACP), which would leak
    one step's policy into later steps of the session.
    """
    matches: list[tuple[str, str]] = []
    for option in options:
        if not isinstance(option, dict):
            continue
        kind = str(option.get("kind", ""))
        option_id = str(option.get("optionId", ""))
        if option_id and kind.startswith(prefer):
            matches.append((kind, option_id))
    for kind, option_id in matches:
        if kind.endswith("_once"):
            return option_id
    return matches[0][1] if matches else None


def permission_kind(params: dict[str, Any]) -> str:
    """What the agent wants to do, as ACP names it: `edit`, `execute`…"""
    permission = params.get("permission")
    if not isinstance(permission, dict):
        permission = {}
    kind = str(permission.get("kind", "")).lower()
    if kind:
        return kind
    tool_call = params.get("toolCall")
    if not isinstance(tool_call, dict):
        tool_call = {}
    return str(tool_call.get("kind", "")).lower()


def decide_permission(
    params: dict[str, Any],
    *,
    policy: PermissionPolicy,
    allow_terminal: bool = False,
) -> dict[str, Any] | None:
    """The answer the policy gives on its own. `None` means a person must decide.

    Lives outside the TUI so the daemon applies policy where the run executes;
    otherwise a run with no attached cockpit would block on a prompt the policy
    already resolves. `None` always under `ask`, and under `deny_writes` when the
    kind does not say whether it writes (`execute`, unknown).
    """
    options = params.get("options")
    if not isinstance(options, list):
        options = []
    kind = permission_kind(params)

    def chosen(prefer: str, fallback: str) -> dict[str, Any]:
        return permission_selected(pick_permission_option(options, prefer=prefer) or fallback)

    if not allow_terminal and (
        "terminal" in kind or "shell" in kind or "bash" in kind or "command" in kind
    ):
        return chosen("reject", "reject-once")

    if policy == "auto_approve":
        return chosen("allow", "allow-once")

    if policy == "deny_writes":
        if kind in _READ_ONLY_KINDS:
            return chosen("allow", "allow-once")
        if kind in _WRITE_KINDS or "write" in kind:
            return chosen("reject", "reject-once")
        return None

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
