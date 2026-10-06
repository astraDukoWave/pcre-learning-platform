"""Entrada ASGI: `uvicorn app.main:app` (el comando vive en `heroku.yml`)."""

from __future__ import annotations

from fastapi import FastAPI

from app.bootstrap import Container, build_container
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.http import health
from app.http.errors import install_error_handlers
from app.http.middleware import RequestContextMiddleware


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
    app.add_middleware(RequestContextMiddleware)
    return app


app = create_app()
