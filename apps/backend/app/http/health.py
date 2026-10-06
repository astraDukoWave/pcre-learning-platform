"""Liveness (`/health`, sin base de datos) y readiness (`/api/v1/ready`)."""

from __future__ import annotations

import logging
from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import BACKEND_DIR
from app.core.errors import ServiceUnavailable
from app.http.deps import ContainerDep

logger = logging.getLogger("app.health")

router = APIRouter()


class HealthOut(BaseModel):
    status: str


class ReadyOut(BaseModel):
    status: str
    migration: str


@lru_cache(maxsize=1)
def expected_migration_head() -> str:
    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    if head is None:
        raise RuntimeError("Alembic no tiene head")
    return head


@router.get("/health", response_model=HealthOut, tags=["ops"])
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/api/v1/ready", response_model=ReadyOut, tags=["ops"])
def ready(container: ContainerDep) -> ReadyOut:
    expected = expected_migration_head()
    try:
        with container.uow() as session:
            session.execute(text("SELECT 1"))
            applied = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:
        logger.warning("ready_db_unavailable", extra={"exception_type": type(exc).__name__})
        raise ServiceUnavailable("La base de datos no responde.", code="db_unavailable") from exc
    if applied != expected:
        logger.warning("ready_migration_mismatch", extra={"applied": applied, "expected": expected})
        raise ServiceUnavailable(
            "La base de datos no está en la migración esperada.", code="migration_mismatch"
        )
    return ReadyOut(status="ready", migration=expected)
