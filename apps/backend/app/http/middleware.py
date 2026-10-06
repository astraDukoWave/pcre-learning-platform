"""Middleware ASGI: `request_id` (`X-Request-ID`) y una línea de log JSON por petición."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Callable

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
