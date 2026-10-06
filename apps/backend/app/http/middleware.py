"""Middleware ASGI: `request_id` (`X-Request-ID`) y una línea de log JSON por petición."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable

from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

logger = logging.getLogger("app.access")

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


ServerErrorHook = Callable[[Scope, BaseException], None]


class RequestContextMiddleware:
    """También atrapa las excepciones no manejadas: responde 500 con el sobre de error y
    el `request_id`, y avisa a `on_server_error` (registro en `error_events`)."""

    def __init__(self, app: ASGIApp, on_server_error: ServerErrorHook | None = None) -> None:
        self.app = app
        self.on_server_error = on_server_error

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        incoming = ""
        for name, value in scope.get("headers", []):
            if name == b"x-request-id":
                incoming = value.decode("latin-1")
                break
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status = {"code": 500, "started": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                status["started"] = 1
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            status["code"] = 500
            logger.error(
                "unhandled_exception",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"status": 500, "error_code": "internal_error"},
            )
            if self.on_server_error is not None:
                try:
                    self.on_server_error(scope, exc)
                except Exception:  # el registro nunca tapa la respuesta
                    logger.exception("server_error_hook_failed")
            if scope["type"] == "http" and not status["started"]:
                body = json.dumps(
                    {
                        "error": {
                            "code": "internal_error",
                            "message": "Algo falló de nuestro lado. Ya quedó registrado.",
                            "request_id": request_id,
                        }
                    }
                ).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            (b"x-request-id", request_id.encode()),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
        finally:
            route = scope.get("route")
            route_path = getattr(route, "path", None) or "unmatched"
            if scope["type"] == "http":
                logger.info(
                    "request",
                    extra={
                        "method": scope.get("method"),
                        "route": route_path,
                        "status": status["code"],
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "user_ref": scope.get("state", {}).get("user_ref"),
                    },
                )
            request_id_var.reset(token)


class SecurityHeadersMiddleware:
    """Cabeceras de `docs/arquitectura.md` §7 en toda respuesta HTTP."""

    def __init__(self, app: ASGIApp, *, csp: str, hsts: bool) -> None:
        self.app = app
        self.headers = [
            (b"content-security-policy", csp.encode()),
            (b"x-content-type-options", b"nosniff"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"microphone=(self), camera=(), geolocation=()"),
            (b"x-frame-options", b"DENY"),
            (b"cross-origin-opener-policy", b"same-origin"),
        ]
        if hsts:
            self.headers.append(
                (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in self.headers if k not in existing]
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_wrapper)


def build_csp(app_origin: str | None) -> str:
    connect = ["'self'"]
    if app_origin:
        connect.append(app_origin.replace("https://", "wss://").replace("http://", "ws://"))
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "media-src 'self' blob:",
        f"connect-src {' '.join(connect)}",
        "font-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
    return "; ".join(directives)


class BodyLimitMiddleware:
    """413 si el cuerpo pasa de 64 KB (JSON) o del límite propio de una ruta (audio)."""

    def __init__(
        self, app: ASGIApp, *, default_limit: int, per_path: dict[str, int] | None = None
    ) -> None:
        self.app = app
        self.default_limit = default_limit
        self.per_path = per_path or {}

    def _limit(self, path: str) -> int:
        for prefix, limit in self.per_path.items():
            if path.startswith(prefix):
                return limit
        return self.default_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return
        limit = self._limit(str(scope.get("path", "")))
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > limit:
                    await _send_413(send)
                    return
        received = 0
        too_large = False

        async def receive_wrapper() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, receive_wrapper, send)
        except _BodyTooLarge:
            await _send_413(send)


class _BodyTooLarge(StarletteHTTPException):
    """Subclase de HTTPException: FastAPI la deja pasar al leer el cuerpo (no la vuelve 400)
    y el manejador de errores responde 413 con el sobre."""

    def __init__(self) -> None:
        super().__init__(status_code=413)


async def _send_413(send: Send) -> None:
    body = json.dumps(
        {
            "error": {
                "code": "payload_too_large",
                "message": "El contenido enviado es demasiado grande.",
                "request_id": request_id_var.get(),
            }
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
