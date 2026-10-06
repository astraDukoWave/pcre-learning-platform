"""Entrada ASGI: `uvicorn app.main:app` (el comando vive en `heroku.yml`)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.types import Scope

from app.bootstrap import Container, build_container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.http import health, test_clock
from app.http.csrf import OriginMiddleware
from app.http.errors import install_error_handlers
from app.http.middleware import (
    BodyLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    build_csp,
)
from app.http.static import mount_frontend
from app.modules.content import router_admin as content_admin
from app.modules.content import router_student as content_student
from app.modules.identity import router as identity_router
from app.modules.insights import router as insights_router
from app.modules.insights.service import InsightsService
from app.modules.practice import router as practice_router
from app.modules.practice import router_assessment
from app.modules.progress import router as progress_router

logger = logging.getLogger("app")

JSON_BODY_LIMIT = 64 * 1024
AUDIO_LIMITS = {"/api/v1/speaking/transcriptions": 2 * 1024 * 1024 + 64 * 1024}


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    container = container or build_container(settings)
    configure_logging(settings.log_level)
    insights = InsightsService(container.uow, container.clock)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Retención de `error_events` (30 días): se limpia al arrancar.
        try:
            insights.purge_old_errors()
        except Exception:
            logger.warning("error_events_purge_skipped")
        yield

    def on_server_error(scope: Scope, status: int, exc: BaseException | None) -> None:
        route = getattr(scope.get("route"), "path", None) or "unmatched"
        insights.record_error(
            request_id=str(scope.get("state", {}).get("request_id", "")),
            route=route,
            status_code=status,
            error_code="internal_error" if exc is not None else f"http_{status}",
            exception_type=type(exc).__name__ if exc is not None else None,
        )

    app = FastAPI(
        lifespan=lifespan,
        title=f"{settings.app_name} API",
        version="1.0.0",
        openapi_url="/api/v1/openapi.json" if settings.app_env != "prod" else None,
        docs_url="/api/v1/docs" if settings.app_env != "prod" else None,
        redoc_url=None,
    )
    app.state.container = container
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(identity_router.router)
    app.include_router(identity_router.admin_router)
    app.include_router(content_student.router)
    app.include_router(practice_router.router)
    app.include_router(router_assessment.router)
    app.include_router(progress_router.router)
    app.include_router(insights_router.router)
    app.include_router(content_admin.reports_router)
    if settings.test_clock_active:
        app.include_router(test_clock.router)
    app.include_router(content_admin.router)
    # Siempre al final: el fallback de la SPA atrapa lo que no reclamó ninguna ruta.
    mount_frontend(app, settings)

    # Orden (de adentro hacia afuera): límite de cuerpo → Origin → cabeceras → request_id.
    app.add_middleware(BodyLimitMiddleware, default_limit=JSON_BODY_LIMIT, per_path=AUDIO_LIMITS)
    app.add_middleware(OriginMiddleware, allowed_origins=settings.allowed_origins)
    app.add_middleware(
        SecurityHeadersMiddleware,
        csp=build_csp(settings.app_origin),
        hsts=settings.app_env == "prod",
    )
    app.add_middleware(RequestContextMiddleware, on_server_error=on_server_error)
    return app


app = create_app()
