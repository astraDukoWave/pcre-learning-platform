"""Dependencias de FastAPI compartidas por los routers: contenedor, sesión y rol."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from app.bootstrap import Container
from app.core.errors import Forbidden, Unauthorized
from app.core.logging import user_ref
from app.http.cookies import SESSION_COOKIE
from app.http.csrf import SAFE_METHODS
from app.modules.identity.service import AuthContext, IdentityService


def get_container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


ContainerDep = Annotated[Container, Depends(get_container)]


def get_identity(container: ContainerDep) -> IdentityService:
    return IdentityService(
        container.uow,
        container.clock,
        container.settings,
        container.passwords,
        container.login_limiter,
    )


IdentityDep = Annotated[IdentityService, Depends(get_identity)]


def current_auth(request: Request, identity: IdentityDep, container: ContainerDep) -> AuthContext:
    """Usuario y rol salen siempre de la sesión. En métodos no seguros exige el token CSRF."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise Unauthorized()
    ctx = identity.authenticate(token)
    if ctx is None:
        raise Unauthorized(
            "Tu sesión terminó. Entra de nuevo para continuar.", code="session_expired"
        )
    request.state.user_ref = user_ref(ctx.user_id, container.settings.log_salt)
    if request.method not in SAFE_METHODS and not identity.csrf_matches(
        ctx, request.headers.get("x-csrf-token")
    ):
        raise Forbidden("Recarga la página para continuar.", code="csrf_invalid")
    return ctx


AuthDep = Annotated[AuthContext, Depends(current_auth)]


def require_admin(ctx: AuthDep) -> AuthContext:
    if ctx.role != "admin":
        raise Forbidden()
    return ctx


AdminDep = Annotated[AuthContext, Depends(require_admin)]
