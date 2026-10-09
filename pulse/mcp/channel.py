"""The MCP `AskQuestion` bridge as the session runner sees it: a `QuestionChannel`.

The daemon hands this adapter to the runner, so `acp/` knows only the port.
"""

from __future__ import annotations

from collections.abc import Callable

from pulse.domain.ports import JsonObject, PromptPort
from pulse.mcp.config import pulse_ask_mcp_server
from pulse.mcp.http_bridge import AskQuestionHttpServer


class McpQuestionChannel:
    """One local HTTP MCP server per agent process, closed with it."""

    def __init__(self) -> None:
        self._server: AskQuestionHttpServer | None = None

    def open(self, prompts: PromptPort, on_question: Callable[[], None]) -> list[JsonObject]:
        self.close()
        self._server = AskQuestionHttpServer(prompt_handler=prompts, on_question=on_question)
        self._server.start()
        return [pulse_ask_mcp_server(url=self._server.url)]

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
