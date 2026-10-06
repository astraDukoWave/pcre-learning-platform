"""Entrada ASGI: `uvicorn app.main:app` (el comando vive en `heroku.yml`)."""

from __future__ import annotations

from fastapi import FastAPI

from app.bootstrap import Container, build_container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.http import health
from app.http.csrf import OriginMiddleware
from app.http.errors import install_error_handlers
from app.http.middleware import (
    BodyLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    build_csp,
)
from app.http.static import mount_frontend
from app.modules.identity import router as identity_router

JSON_BODY_LIMIT = 64 * 1024
AUDIO_LIMITS = {"/api/v1/speaking/transcriptions": 2 * 1024 * 1024 + 64 * 1024}


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    settings = settings or (container.settings if container else get_settings())
    container = container or build_container(settings)
    configure_logging(settings.log_level)

    app = FastAPI(
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
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
