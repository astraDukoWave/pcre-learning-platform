"""Único punto de composición: construye adaptadores y servicios desde `Settings`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Engine

from app.core.clock import Clock, OffsetClock, SystemClock
from app.core.config import Settings
from app.core.security import Passwords
from app.db.engine import create_db_engine
from app.db.session import make_sessionmaker
from app.db.uow import UnitOfWorkFactory
from app.modules.identity.domain import SlidingWindowLimiter

# Login: 5 intentos por minuto y 20 por hora, por email y por IP (§7).
LOGIN_LIMITS = ((5, 60), (20, 3600))


@dataclass
class Container:
    settings: Settings
    uow: UnitOfWorkFactory
    clock: Clock
    engine: Engine | None = None
    passwords: Passwords = field(default_factory=Passwords)
    login_limiter: SlidingWindowLimiter = field(
        default_factory=lambda: SlidingWindowLimiter(LOGIN_LIMITS)
    )
    extras: dict[str, Any] = field(default_factory=dict)
    # Capacidades con costo (MVP-02) cuyo proveedor, real o doble, está configurado.
    ready_providers: frozenset[str] = frozenset()

    def provider_ready(self, capability: str) -> bool:
        return capability in self.ready_providers


def build_container(settings: Settings) -> Container:
    engine = create_db_engine(settings)
    clock: Clock = OffsetClock() if settings.test_clock_active else SystemClock()
    return Container(
        settings=settings,
        uow=UnitOfWorkFactory(make_sessionmaker(engine)),
        clock=clock,
        engine=engine,
    )
