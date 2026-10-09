from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pulse.domain.ports import JsonObject
from pulse.replies import wording
from pulse.replies.acp_payloads import PermissionOption, PermissionRequest
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


_READ_ONLY_KINDS = frozenset({"read", "search", "fetch", "think"})
_WRITE_KINDS = frozenset({"edit", "delete", "move"})
_TERMINAL_MARKERS = ("terminal", "shell", "bash", "command")


def build_permission_choices(options: Sequence[PermissionOption]) -> list[tuple[str, str]]:
    """Permission request options, lettered as the dock shows them."""
    shown = [option for option in options if option.choice_id]
    if not shown:
        return [
            ("allow-once", format_option_label(0, wording.ALLOW_ONCE)),
            ("reject-once", format_option_label(1, wording.REJECT_ONCE)),
        ]
    return [
        (option.choice_id, format_option_label(index, option.label()))
        for index, option in enumerate(shown)
    ]


def permission_prompt_text(request: PermissionRequest) -> str:
    parts: list[str] = []
    for part in (request.title, request.description, request.tool_title):
        if part and part not in parts:
            parts.append(part)
    if not parts:
        return wording.PERMISSION_PROMPT_FALLBACK
    return "\n".join(parts)


def permission_selected(option_id: str) -> JsonObject:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def permission_cancelled() -> JsonObject:
    return {"outcome": {"outcome": "cancelled"}}


def pick_permission_option(options: Sequence[PermissionOption], *, prefer: str) -> str | None:
    """First option matching `prefer`, with `*_once` ahead of `*_always`.

    `allow_always` makes the agent remember the choice (ACP), which would leak
    one step's policy into later steps of the session.
    """
    matches = [option for option in options if option.option_id and option.kind.startswith(prefer)]
    once = [option for option in matches if option.kind.endswith("_once")]
    preferred = once or matches
    return preferred[0].option_id if preferred else None


def decide_permission(
    params: Mapping[str, object],
    *,
    policy: PermissionPolicy,
    allow_terminal: bool = False,
) -> JsonObject | None:
    """The answer the policy gives on its own. `None` means a person must decide.

    Lives outside the TUI so the daemon applies policy where the run executes;
    otherwise a run with no attached cockpit would block on a prompt the policy
    already resolves. `None` always under `ask`, and under `deny_writes` when the
    kind does not say whether it writes (`execute`, unknown).
    """
    request = PermissionRequest.parse(params)
    kind = request.kind

    def chosen(prefer: str, fallback: str) -> JsonObject:
        return permission_selected(
            pick_permission_option(request.options, prefer=prefer) or fallback
        )

    if not allow_terminal and any(marker in kind for marker in _TERMINAL_MARKERS):
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


def decide_permission_call(
    args: Sequence[object], kwargs: Mapping[str, object]
) -> JsonObject | None:
    """`decide_permission` for a `respond_to_permission(params, *, policy, allow_terminal)` call.

    The live gate and the run log read the call through here, so the log never
    shows as asked a permission the policy answered, nor drops one a person saw.
    """
    params = args[0] if args else kwargs.get("params")
    if not isinstance(params, Mapping):
        return None
    policy = kwargs.get("policy")
    return decide_permission(
        params,
        policy=parse_policy(policy) if isinstance(policy, str) else "ask",
        allow_terminal=bool(kwargs.get("allow_terminal", False)),
    )
