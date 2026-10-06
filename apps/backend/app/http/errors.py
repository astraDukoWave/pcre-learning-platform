"""Sobre de errores único: `{"error": {"code", "message", "request_id"}}` (§6.1)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError
from app.core.logging import request_id_var

logger = logging.getLogger("app.http")

_HTTP_CODES = {
    400: ("bad_request", "La petición no es válida."),
    401: ("unauthorized", "Necesitas entrar para continuar."),
    403: ("forbidden", "No tienes acceso a esta sección."),
    404: ("not_found", "No encontramos esto."),
    405: ("method_not_allowed", "Esta operación no está permitida aquí."),
    413: ("payload_too_large", "El contenido enviado es demasiado grande."),
    422: ("validation_error", "Revisa los datos enviados."),
    429: ("rate_limited", "Espera un momento antes de intentarlo de nuevo."),
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    **extra: object,
) -> JSONResponse:
    body: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": request_id_var.get(),
    }
    body.update(extra)
    return JSONResponse({"error": body}, status_code=status_code, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.expected:
            request.state.error_expected = True
        level = logging.WARNING if exc.status_code in (403, 429) else logging.INFO
        logger.log(level, "app_error", extra={"error_code": exc.code, "status": exc.status_code})
        return error_response(exc.status_code, exc.code, exc.message, exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(
            exc.status_code, ("error", "La petición no se pudo completar.")
        )
        headers = dict(exc.headers) if exc.headers else None
        return error_response(exc.status_code, code, message, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"loc": [str(p) for p in err.get("loc", ())], "type": err.get("type", "")}
            for err in exc.errors()
        ]
        logger.info("validation_error", extra={"error_code": "validation_error", "status": 422})
        return error_response(422, "validation_error", "Revisa los datos enviados.", fields=fields)
