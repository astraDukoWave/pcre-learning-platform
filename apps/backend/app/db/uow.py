"""Unidad de trabajo: una transacción corta por caso de uso, con commit al final."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker


class UnitOfWorkFactory:
    """`with uow() as session:` hace commit si el bloque termina sin excepción."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    @contextmanager
    def __call__(self) -> Iterator[Session]:
        session = self._factory()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
