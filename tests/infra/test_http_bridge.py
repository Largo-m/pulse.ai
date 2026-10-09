import http.client
import json
import urllib.parse
import urllib.request

import pytest

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
    # The URL is the bridge this test just started on localhost.
    request = urllib.request.Request(  # noqa: S310
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - http on loopback, the bridge under test
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
                        {
                            "id": "q1",
                            "prompt": "Qual stack?",
                            "options": [{"id": "py", "label": "Python"}],
                        }
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


_ASK = {
    "jsonrpc": "2.0",
    "id": 9,
    "method": "tools/call",
    "params": {
        "name": "AskQuestion",
        "arguments": {"questions": [{"id": "q", "prompt": "Paste your token", "options": []}]},
    },
}


def _raw_post(url, payload, headers):
    """Post with headers urllib would rewrite (Host) or never send (Origin)."""
    parsed = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        connection.request("POST", parsed.path, body=json.dumps(payload), headers=headers)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({"Origin": "https://attacker.example"}, id="browser-origin"),
        pytest.param({"Host": "attacker.example"}, id="dns-rebinding-host"),
    ],
)
def test_http_bridge_refuses_requests_a_web_page_could_send(headers):
    """The MCP spec requires validating Origin: the bridge listens on loopback,
    and a page in the user's browser could otherwise POST a text/plain body that
    puts a fake agent question (\"paste your token\") in front of the user.
    """
    handler = _StubHandler()
    server = AskQuestionHttpServer(prompt_handler=handler)
    server.start()
    try:
        status, _ = _raw_post(server.url, _ASK, {"Content-Type": "text/plain", **headers})
    finally:
        server.close()

    assert status == 403
    assert handler.calls == []


def test_http_bridge_serves_the_agent_on_its_own_loopback_host():
    handler = _StubHandler()
    server = AskQuestionHttpServer(prompt_handler=handler)
    server.start()
    try:
        host = urllib.parse.urlsplit(server.url).netloc
        status, _ = _raw_post(server.url, _ASK, {"Content-Type": "application/json", "Host": host})
    finally:
        server.close()

    assert status == 200
    assert len(handler.calls) == 1
