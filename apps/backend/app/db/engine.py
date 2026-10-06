"""Engine síncrono con psycopg 3 (ADR-05)."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine

from app.core.config import Settings


def create_db_engine(settings: Settings) -> Engine:
    # 5 + 5 deja margen dentro de las 20 conexiones de Essential-0 para la release
    # phase y los one-off dynos (`docs/arquitectura.md` §5).
    return create_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_timeout=10,
        connect_args={"connect_timeout": 5, "application_name": settings.app_name.lower()},
    )
