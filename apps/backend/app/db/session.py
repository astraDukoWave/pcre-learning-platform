"""Fábrica de sesiones de SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker


def make_sessionmaker(
    bind: Engine | Connection, *, savepoints: bool = False
) -> sessionmaker[Session]:
    if savepoints:
        # Pruebas: cada `commit()` del código se vuelve un savepoint dentro de la
        # transacción externa, que se revierte al terminar la prueba.
        return sessionmaker(
            bind=bind,
            expire_on_commit=False,
            autoflush=True,
            join_transaction_mode="create_savepoint",
        )
    return sessionmaker(bind=bind, expire_on_commit=False, autoflush=True)
