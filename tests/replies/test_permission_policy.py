from __future__ import annotations

import pytest

from pulse.replies.permission import decide_permission, decide_permission_call, parse_policy

OPTIONS = [
    {"optionId": "always", "kind": "allow_always"},
    {"optionId": "once", "kind": "allow_once"},
    {"optionId": "no", "kind": "reject_once"},
]


def _decide(kind: str, policy: str) -> str | None:
    decided = decide_permission({"options": OPTIONS, "toolCall": {"kind": kind}}, policy=policy)
    return None if decided is None else decided["outcome"]["optionId"]


@pytest.mark.parametrize("kind", ["read", "search", "fetch", "think"])
def test_deny_writes_allows_read_only_kinds_once(kind: str) -> None:
    assert _decide(kind, "deny_writes") == "once"


@pytest.mark.parametrize("kind", ["edit", "delete", "move"])
def test_deny_writes_rejects_kinds_that_change_files(kind: str) -> None:
    assert _decide(kind, "deny_writes") == "no"


@pytest.mark.parametrize("kind", ["execute", "other", ""])
def test_deny_writes_asks_a_person_when_the_kind_may_write(kind: str) -> None:
    """Claude's Bash arrives as `execute`: auto-approving it bypassed the policy."""
    assert _decide(kind, "deny_writes") is None


def test_auto_approve_prefers_allow_once_over_allow_always() -> None:
    assert _decide("edit", "auto_approve") == "once"


@pytest.mark.parametrize("value", ["ask", "auto_approve", "deny_writes", " deny_writes "])
def test_a_known_policy_is_kept(value: str):
    assert parse_policy(value) == value.strip()


@pytest.mark.parametrize("value", ["", "allow_all", "AUTO_APPROVE", "yes"])
def test_an_unknown_policy_asks_instead_of_allowing(value: str):
    """A typo in the config must never widen what the agent may do on its own."""
    assert parse_policy(value) == "ask"


def _call_choice(args: tuple[object, ...], kwargs: dict[str, object]) -> str | None:
    decided = decide_permission_call(args, kwargs)
    return None if decided is None else decided["outcome"]["optionId"]


READ = {"options": OPTIONS, "toolCall": {"kind": "read"}}
SHELL = {"options": OPTIONS, "toolCall": {"kind": "bash"}}


def test_a_call_reads_params_by_position_or_by_name() -> None:
    """The port takes `params` either way; both must reach the same decision."""
    assert _call_choice((READ,), {"policy": "deny_writes"}) == "once"
    assert _call_choice((), {"params": READ, "policy": "deny_writes"}) == "once"


@pytest.mark.parametrize("params", [None, "read", ["read"]])
def test_a_call_without_params_is_left_to_a_person(params: object) -> None:
    assert decide_permission_call((), {"params": params, "policy": "auto_approve"}) is None


@pytest.mark.parametrize("policy", [None, 1, b"auto_approve"])
def test_a_call_whose_policy_is_not_text_asks(policy: object) -> None:
    """Asking is never unsafe: a policy the call cannot name is `ask`."""
    assert decide_permission_call((READ,), {"policy": policy}) is None


def test_a_call_without_a_policy_asks() -> None:
    assert decide_permission_call((READ,), {}) is None


def test_a_call_keeps_the_terminal_veto_unless_it_allows_a_terminal() -> None:
    assert _call_choice((SHELL,), {"policy": "auto_approve"}) == "no"
    assert _call_choice((SHELL,), {"policy": "auto_approve", "allow_terminal": True}) == "once"
