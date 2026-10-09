"""What the permission policy answers on its own, and the exact wire answer it sends.

The agent reads the option id literally: a misspelt fallback id or a lost
terminal veto is an answer the agent either ignores or obeys wrongly.
"""

from __future__ import annotations

import pytest

from pulse.replies import wording
from pulse.replies.acp_payloads import PermissionRequest
from pulse.replies.permission import (
    build_permission_choices,
    decide_permission,
    permission_cancelled,
    permission_prompt_text,
    permission_selected,
)

OPTIONS = [
    {"optionId": "always", "kind": "allow_always"},
    {"optionId": "once", "kind": "allow_once"},
    {"optionId": "no", "kind": "reject_once"},
]
TERMINAL_KINDS = ["terminal", "shell", "bash", "run_command", "execute_command"]


def _decide(kind: str, policy: str, *, options=OPTIONS, allow_terminal: bool = False):
    return decide_permission(
        {"options": options, "toolCall": {"kind": kind}},
        policy=policy,
        allow_terminal=allow_terminal,
    )


@pytest.mark.parametrize("policy", ["ask", "auto_approve", "deny_writes"])
@pytest.mark.parametrize("kind", TERMINAL_KINDS)
def test_the_terminal_is_vetoed_under_every_policy(kind: str, policy: str):
    assert _decide(kind, policy) == {"outcome": {"outcome": "selected", "optionId": "no"}}


def test_a_client_that_runs_the_terminal_lets_the_policy_decide_it():
    assert _decide("terminal", "auto_approve", allow_terminal=True) == permission_selected("once")
    assert _decide("terminal", "ask", allow_terminal=True) is None


@pytest.mark.parametrize(
    ("kind", "policy", "expected"),
    [
        ("terminal", "ask", "reject-once"),
        ("edit", "auto_approve", "allow-once"),
        ("read", "deny_writes", "allow-once"),
        ("edit", "deny_writes", "reject-once"),
        ("write_file", "deny_writes", "reject-once"),
    ],
)
def test_without_a_matching_option_the_standard_id_is_answered(kind, policy, expected):
    """An agent that offers no options still gets an id ACP defines, not a blank."""
    assert _decide(kind, policy, options=[]) == {
        "outcome": {"outcome": "selected", "optionId": expected}
    }


def test_a_kind_that_writes_by_name_is_rejected_under_deny_writes():
    assert _decide("write_text_file", "deny_writes") == permission_selected("no")


def test_the_wire_answers_have_the_shape_acp_expects():
    assert permission_selected("x") == {"outcome": {"outcome": "selected", "optionId": "x"}}
    assert permission_cancelled() == {"outcome": {"outcome": "cancelled"}}


def test_a_request_without_options_offers_allow_and_reject():
    assert build_permission_choices(()) == [
        ("allow-once", f"A) {wording.ALLOW_ONCE}"),
        ("reject-once", f"B) {wording.REJECT_ONCE}"),
    ]


def test_the_prompt_lists_each_distinct_line_in_order():
    request = PermissionRequest.parse(
        {
            "permission": {"title": "Edit app.py", "description": "Adds a route"},
            "toolCall": {"title": "Edit app.py"},
        }
    )

    assert permission_prompt_text(request) == "Edit app.py\nAdds a route"


def test_the_tool_title_is_shown_when_it_is_new():
    request = PermissionRequest.parse(
        {"permission": {"title": "Edit"}, "toolCall": {"title": "app.py"}}
    )

    assert permission_prompt_text(request) == "Edit\napp.py"


def test_a_request_with_nothing_to_say_uses_the_fallback_text():
    assert permission_prompt_text(PermissionRequest.parse({})) == (
        wording.PERMISSION_PROMPT_FALLBACK
    )
