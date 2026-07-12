from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import time

from pulse.tui.adapters.prompt_bridge import PromptBridge, PromptKind, TextualPromptHandler


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
        deadline = time.time() + 2
        request = None
        while time.time() < deadline:
            request = bridge.poll()
            if request is not None:
                break
            time.sleep(0.01)
        assert request is not None
        assert request.kind == PromptKind.SELECT
        assert request.future is not None
        request.future.set_result("b")
        assert future.result(timeout=2) == "b"


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
