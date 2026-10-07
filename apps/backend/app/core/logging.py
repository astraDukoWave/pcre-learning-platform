"""Logs JSON de una línea, sin datos personales (`docs/arquitectura.md` §7)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Claves que nunca salen en un log, aunque alguien las pase en `extra`.
FORBIDDEN_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "new_password",
        "password_confirm",
        "token",
        "token_hash",
        "csrf",
        "csrf_token",
        "cookie",
        "cookies",
        "set_cookie",
        "authorization",
        "email",
        "response",
        "answer",
        "answers",
        "transcript",
        "audio",
        "body",
        "api_key",
    }
)

_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None)).keys()
    | {"message", "asctime", "taskName"}
)

_ALLOWED_ORDER = ("ts", "level", "msg", "logger", "request_id")


def user_ref(user_id: object, salt: str) -> str:
    """Hash corto y salado del id: permite seguir a un usuario en los logs sin exponerlo."""
    digest = hmac.new(salt.encode(), str(user_id).encode(), hashlib.sha256).hexdigest()
    return digest[:12]


def _is_forbidden(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return lowered in FORBIDDEN_KEYS


def _clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if not _is_forbidden(str(k))}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "msg": record.getMessage(),
            "logger": record.name,
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_ATTRS or key in payload or key.startswith("_"):
                continue
            if _is_forbidden(key):
                continue
            payload[key] = _clean(value)
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
            payload["trace"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).disabled = True
    # En DEBUG, `websockets` registra las cabeceras del handshake (incluida la llave del
    # proveedor de voz): nunca baja de INFO.
    logging.getLogger("websockets").setLevel(max(logging.INFO, root.level))
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
