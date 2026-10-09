from __future__ import annotations

import secrets

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from pulse.api.browser_guard import SECURITY_HEADERS

UNAUTHORIZED = 401
BEARER = "bearer"
_REFUSAL_HEADERS = {
    "WWW-Authenticate": "Bearer",
    **{name.decode(): value.decode() for name, value in SECURITY_HEADERS},
}


class TokenGuard:
    """Lets through only requests that carry the daemon's bearer token.

    Wraps the TCP listener alone: loopback keeps the network out but not other
    users of the machine, and the `0600` meta file that holds the token is the
    TCP equivalent of the `0600` Unix socket (ADR 0005). Outermost, so a
    refused request never reaches a route.
    """

    def __init__(self, app: ASGIApp, token: str) -> None:
        if not token:
            raise ValueError("the daemon token must not be empty")
        self.app = app
        self._token = token.encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan" or self._authorized(scope):
            await self.app(scope, receive, send)
            return
        refusal = JSONResponse(
            status_code=UNAUTHORIZED,
            content={"detail": "missing or invalid daemon token"},
            headers=_REFUSAL_HEADERS,
        )
        await refusal(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        for name, value in scope["headers"]:
            if name != b"authorization":
                continue
            scheme, _, credential = value.partition(b" ")
            return scheme.lower() == BEARER.encode() and secrets.compare_digest(
                credential, self._token
            )
        return False
