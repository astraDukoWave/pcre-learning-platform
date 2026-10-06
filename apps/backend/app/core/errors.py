"""Errores tipados con código estable. Los servicios los lanzan; `app.http.errors` los traduce."""

from __future__ import annotations


class AppError(Exception):
    status_code: int = 400
    code: str = "bad_request"
    default_message: str = "La petición no es válida."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        self.headers = headers or {}
        super().__init__(self.message)


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    default_message = "Necesitas entrar para continuar."


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"
    default_message = "Esta sección es para el equipo editorial."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    default_message = "No encontramos esto."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    default_message = "La operación entra en conflicto con el estado actual."


class PayloadTooLarge(AppError):
    status_code = 413
    code = "payload_too_large"
    default_message = "El contenido enviado es demasiado grande."


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"
    default_message = "Revisa los datos enviados."


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"
    default_message = "Espera un momento antes de intentarlo de nuevo."

    def __init__(self, retry_after_seconds: int, message: str | None = None) -> None:
        super().__init__(message, headers={"Retry-After": str(max(1, retry_after_seconds))})
        self.retry_after_seconds = retry_after_seconds


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
    default_message = "El servicio no está disponible ahora."
