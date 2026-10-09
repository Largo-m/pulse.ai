from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

FORBIDDEN = 403
SECURITY_HEADERS: tuple[tuple[bytes, bytes], ...] = (
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
)


class BrowserGuard:
    """Refuses any request a browser sent and hardens every response.

    The CLI and the TUI never send `Origin`; browsers always do on cross-site
    and POST requests. A no-cors POST needs no preflight, so CORS alone would
    only hide the response while the route still ran (CSRF against loopback).
    Pure ASGI, so SSE streams pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_hardened(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        if any(name == b"origin" for name, _ in scope["headers"]):
            refusal = JSONResponse(
                status_code=FORBIDDEN, content={"detail": "browser requests are not accepted"}
            )
            await refusal(scope, receive, send_hardened)
            return
        await self.app(scope, receive, send_hardened)
