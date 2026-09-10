import json
import urllib.request

from pulse.mcp.http_bridge import AskQuestionHttpServer


class _StubHandler:
    def __init__(self):
        self.calls = []

    def respond_to_ask_question(self, params):
        self.calls.append(params)
        return {
            "outcome": {
                "outcome": "answered",
                "answers": [{"questionId": "q1", "selectedOptionIds": ["py"]}],
            }
        }


def _post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        status = response.status
        body = response.read().decode("utf-8")
    return status, body


def test_http_bridge_initialize_and_tools_list():
    server = AskQuestionHttpServer(prompt_handler=_StubHandler())
    server.start()
    try:
        url = server.url
        assert url.startswith("http://127.0.0.1:")

        status, body = _post(url, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert status == 200
        result = json.loads(body)["result"]
        assert result["capabilities"] == {"tools": {}}

        status, body = _post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert status == 200
        tools = json.loads(body)["result"]["tools"]
        assert tools[0]["name"] == "AskQuestion"
    finally:
        server.close()


def test_http_bridge_tools_call_invokes_prompt_handler():
    handler = _StubHandler()
    counter = {"n": 0}
    server = AskQuestionHttpServer(
        prompt_handler=handler,
        on_question=lambda: counter.__setitem__("n", counter["n"] + 1),
    )
    server.start()
    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "AskQuestion",
                "arguments": {
                    "questions": [
                        {"id": "q1", "prompt": "Qual stack?", "options": [{"id": "py", "label": "Python"}]}
                    ]
                },
            },
        }
        status, body = _post(server.url, payload)
        assert status == 200
        result = json.loads(body)["result"]
        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert "answered" in text
        assert handler.calls
        assert counter["n"] == 1
    finally:
        server.close()


def test_http_bridge_notification_returns_202():
    server = AskQuestionHttpServer(prompt_handler=_StubHandler())
    server.start()
    try:
        status, body = _post(server.url, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        assert status == 202
        assert body == ""
    finally:
        server.close()
