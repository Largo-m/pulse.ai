from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from pulse import __version__
from pulse.api import config_routes, history_routes, run_routes, system_routes
from pulse.api.browser_guard import BrowserGuard
from pulse.daemon.runs import RunManager

TRUSTED_HOSTS = ("127.0.0.1", "localhost", "pulse")
_log = logging.getLogger(__name__)
ROUTERS = (system_routes.router, config_routes.router, run_routes.router, history_routes.router)


async def _on_error(request: Request, exc: Exception) -> JSONResponse:
    _log.error("%s %s failed", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


def create_app(manager: RunManager | None = None) -> FastAPI:
    app = FastAPI(title="Pulse Engine", version=__version__)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(TRUSTED_HOSTS))
    app.add_middleware(BrowserGuard)
    app.state.runs = manager or RunManager()
    for router in ROUTERS:
        app.include_router(router)
    app.add_exception_handler(Exception, _on_error)
    return app
