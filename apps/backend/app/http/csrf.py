"""`Origin` (o `Referer`) obligatorio y permitido en todo método no seguro de la API.

El token CSRF (`X-CSRF-Token`) se verifica en `current_auth` (`app/http/deps.py`), que ya
carga la sesión. Las rutas públicas de acceso (login, aceptar invitación, reset) no tienen
token todavía: las protege este chequeo de origen.
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.logging import request_id_var

logger = logging.getLogger("app.http.csrf")

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _origin_of(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


class OriginMiddleware:
    def __init__(self, app: ASGIApp, allowed_origins: tuple[str, ...]) -> None:
        self.app = app
        self.allowed = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        if not str(scope.get("path", "")).startswith("/api/"):
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        origin = headers.get("origin") or _origin_of(headers.get("referer", "")) or ""
        if origin.rstrip("/") in self.allowed:
            await self.app(scope, receive, send)
            return
        logger.warning("origin_rejected", extra={"origin": origin[:100], "status": 403})
        body = json.dumps(
            {
                "error": {
                    "code": "origin_invalid",
                    "message": "Recarga la página para continuar.",
                    "request_id": request_id_var.get(),
                }
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
