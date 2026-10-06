"""Arnés de pruebas: PostgreSQL real, una transacción revertida por prueba y sin red.

- La base `pcre_test` se migra a head una vez por sesión.
- Cada prueba corre dentro de una transacción externa; los `commit()` del código se
  vuelven savepoints y todo se revierte al final.
- `pytest-socket` (en `addopts`) bloquea cualquier host que no sea localhost.
"""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://pcre:pcre@127.0.0.1:5432/pcre_test")
os.environ.setdefault("LOG_SALT", "test-salt")

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine, text
from sqlalchemy.orm import Session

from app.bootstrap import Container
from app.core.clock import FakeClock
from app.core.config import BACKEND_DIR, Settings
from app.db.engine import create_db_engine
from app.db.session import make_sessionmaker
from app.db.uow import UnitOfWorkFactory
from app.main import create_app

TEST_ORIGIN = "http://localhost:5173"


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["skip_logging_config"] = True
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def reset_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(app_env="test", log_salt="test-salt")


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    engine = create_db_engine(settings)
    reset_schema(engine)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    conn = engine.connect()
    trans = conn.begin()
    try:
        yield conn
    finally:
        trans.rollback()
        conn.close()


@pytest.fixture
def uow(connection: Connection) -> UnitOfWorkFactory:
    return UnitOfWorkFactory(make_sessionmaker(connection, savepoints=True))


@pytest.fixture
def db(connection: Connection) -> Iterator[Session]:
    """Sesión para preparar y revisar datos dentro de la misma transacción de la prueba."""
    session = make_sessionmaker(connection, savepoints=True)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def container(settings: Settings, uow: UnitOfWorkFactory, clock: FakeClock) -> Container:
    return Container(settings=settings, uow=uow, clock=clock)


@pytest.fixture
def app(container: Container) -> FastAPI:
    return create_app(container.settings, container=container)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, base_url="https://testserver", headers={"Origin": TEST_ORIGIN}) as c:
        yield c


def backend_path(*parts: str) -> Path:
    return BACKEND_DIR.joinpath(*parts)
