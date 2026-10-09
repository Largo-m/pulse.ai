from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from pulse.replies.acp_payloads import PermissionRequest
from pulse.tui.adapters.prompt_bridge import (
    PromptBridge,
    PromptKind,
    PromptRequest,
    TextualPromptHandler,
    build_permission_choices,
    format_prompt_reply,
)


def test_prompt_bridge_request_roundtrip():
    bridge = PromptBridge()

    def worker():
        return bridge.select(
            "Escolha",
            [("a", "Alpha"), ("b", "Beta")],
            title="Test",
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        request = bridge.poll(timeout=2)
        assert request is not None
        assert request.kind == PromptKind.SELECT
        assert request.future is not None
        request.future.set_result("b")
        assert future.result(timeout=2) == "b"


def test_build_permission_choices_uses_questionnaire_letters():
    choices = build_permission_choices(
        PermissionRequest.parse(
            {
                "options": [
                    {"optionId": "allow-once", "kind": "allow_once"},
                    {"optionId": "allow-always", "kind": "allow_always"},
                    {"optionId": "reject-once", "kind": "reject_once"},
                ]
            }
        ).options
    )
    assert choices == [
        ("allow-once", "A) Permitir esta vez"),
        ("allow-always", "B) Sempre permitir"),
        ("reject-once", "C) Recusar"),
    ]


def test_textual_prompt_handler_permission_ask_uses_select():
    bridge = PromptBridge()
    handler = TextualPromptHandler(bridge)

    def worker():
        return handler.respond_to_permission(
            {
                "permission": {"title": "Editar app.py", "kind": "edit"},
                "options": [
                    {"optionId": "allow-once", "kind": "allow_once"},
                    {"optionId": "reject-once", "kind": "reject_once"},
                ],
            },
            policy="ask",
        )

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        request = bridge.poll(timeout=2)
        assert request is not None
        assert request.kind == PromptKind.SELECT
        assert request.title == "Permissão"
        assert request.prompt == "Editar app.py"
        assert request.choices[0] == ("allow-once", "A) Permitir esta vez")
        assert request.future is not None
        request.future.set_result("allow-once")
        result = future.result(timeout=2)
    assert result["outcome"]["outcome"] == "selected"
    assert result["outcome"]["optionId"] == "allow-once"


def test_textual_prompt_handler_permission_deny_writes_has_no_path_exception():
    """No folder belongs to Pulse: deny_writes rejects every write."""
    bridge = PromptBridge()
    handler = TextualPromptHandler(bridge)
    result = handler.respond_to_permission(
        {
            "permission": {"title": "Write plano", "kind": "write"},
            "toolCall": {"kind": "edit", "rawInput": {"path": "/repo/docs/PLANO.md"}},
            "options": [
                {"optionId": "allow-once", "kind": "allow_once"},
                {"optionId": "reject-once", "kind": "reject_once"},
            ],
        },
        policy="deny_writes",
    )
    assert result["outcome"]["outcome"] == "selected"
    assert result["outcome"]["optionId"] == "reject-once"


def test_textual_prompt_handler_permission_deny_writes_blocks_app_code():
    bridge = PromptBridge()
    handler = TextualPromptHandler(bridge)
    result = handler.respond_to_permission(
        {
            "permission": {"title": "Editar app.py", "kind": "edit"},
            "toolCall": {"kind": "edit", "rawInput": {"path": "/repo/app.py"}},
            "options": [
                {"optionId": "allow-once", "kind": "allow_once"},
                {"optionId": "reject-once", "kind": "reject_once"},
            ],
        },
        policy="deny_writes",
    )
    assert result["outcome"]["outcome"] == "selected"
    assert result["outcome"]["optionId"] == "reject-once"


def test_textual_prompt_handler_permission_auto_approve():
    bridge = PromptBridge()
    handler = TextualPromptHandler(bridge)
    result = handler.respond_to_permission(
        {
            "permission": {"title": "Write file", "kind": "edit"},
            "options": [
                {"optionId": "allow-once", "kind": "allow_once"},
                {"optionId": "reject-once", "kind": "reject_once"},
            ],
        },
        policy="auto_approve",
    )
    assert result["outcome"]["outcome"] == "selected"
    assert result["outcome"]["optionId"] == "allow-once"


def test_format_prompt_reply_maps_choices_and_cancel():
    request = PromptRequest(
        kind=PromptKind.SELECT,
        title="Questionário",
        prompt="Qual o tamanho?",
        choices=[("small", "A) small"), ("medium", "B) medium")],
    )
    assert format_prompt_reply(request, "medium") == "B) medium"
    assert format_prompt_reply(request, None) == "Cancelado"
    text = PromptRequest(kind=PromptKind.TEXT, title="", prompt="Descreva", choices=[])
    assert format_prompt_reply(text, "  dashboard  ") == "dashboard"
    confirm = PromptRequest(kind=PromptKind.CONFIRM, title="", prompt="Ok?", choices=[])
    assert format_prompt_reply(confirm, True) == "Sim"
    assert format_prompt_reply(confirm, False) == "Não"
    multi = PromptRequest(
        kind=PromptKind.MULTI_SELECT,
        title="",
        prompt="Escolha",
        choices=[("a", "Alpha"), ("b", "Beta")],
    )
    assert format_prompt_reply(multi, ["a", "b"]) == "Alpha, Beta"
