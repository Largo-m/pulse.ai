from __future__ import annotations

import pytest

from pulse.replies.permission import decide_permission, parse_policy

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
