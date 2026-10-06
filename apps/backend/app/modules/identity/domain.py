"""Reglas puras de identidad: contraseñas, vencimientos, invitaciones y límite de intentos."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

PASSWORD_MIN = 10
PASSWORD_MAX = 128
LAST_SEEN_GRANULARITY = timedelta(minutes=5)

GOAL_PURPOSES = ("work", "studies", "certification", "other", "unknown")
TARGET_EXAMS = (
    "toefl_ibt",
    "ielts_academic",
    "cambridge_b2_first",
    "toefl_itp",
    "other",
    "unknown",
)
SELF_LEVELS = ("A2", "B1", "B2", "unknown")
REVOKE_REASONS = ("logout", "rotated", "password_reset", "admin", "account_deleted")

InvitationStatus = Literal["valid", "expired", "consumed"]


def normalize_email(email: str) -> str:
    return email.strip().lower()


def password_problems(password: str, email: str) -> list[str]:
    """Mínimo 10 y máximo 128 caracteres, sin reglas de composición; distinta del email."""
    problems: list[str] = []
    if len(password) < PASSWORD_MIN:
        problems.append("password_too_short")
    if len(password) > PASSWORD_MAX:
        problems.append("password_too_long")
    if password.strip().lower() == normalize_email(email):
        problems.append("password_equals_email")
    return problems


@dataclass(frozen=True)
class SessionWindow:
    created_at: datetime
    last_seen_at: datetime
    absolute_expires_at: datetime
    idle_expires_at: datetime
    revoked_at: datetime | None = None


def open_session_window(now: datetime, absolute_days: int, idle_hours: int) -> SessionWindow:
    absolute = now + timedelta(days=absolute_days)
    idle = min(now + timedelta(hours=idle_hours), absolute)
    return SessionWindow(
        created_at=now, last_seen_at=now, absolute_expires_at=absolute, idle_expires_at=idle
    )


def session_is_active(window: SessionWindow, now: datetime) -> bool:
    if window.revoked_at is not None:
        return False
    return now < window.absolute_expires_at and now < window.idle_expires_at


def refreshed_window(window: SessionWindow, now: datetime, idle_hours: int) -> SessionWindow | None:
    """Nueva ventana de inactividad si pasaron 5 minutos desde el último registro; si no,
    `None` (así `last_seen_at` se escribe como máximo cada 5 minutos)."""
    if now - window.last_seen_at < LAST_SEEN_GRANULARITY:
        return None
    idle = min(now + timedelta(hours=idle_hours), window.absolute_expires_at)
    return SessionWindow(
        created_at=window.created_at,
        last_seen_at=now,
        absolute_expires_at=window.absolute_expires_at,
        idle_expires_at=idle,
        revoked_at=window.revoked_at,
    )


def one_time_token_status(
    expires_at: datetime, consumed_at: datetime | None, now: datetime
) -> InvitationStatus:
    if consumed_at is not None:
        return "consumed"
    if now >= expires_at:
        return "expired"
    return "valid"


class SlidingWindowLimiter:
    """Límite de intentos en memoria del proceso (un dyno; trigger del §2 para moverlo a
    PostgreSQL). Cada clave admite `count` eventos por ventana de `seconds`."""

    def __init__(self, limits: tuple[tuple[int, int], ...]) -> None:
        self._limits = limits
        self._longest = max(seconds for _, seconds in limits)
        self._events: dict[str, deque[datetime]] = {}
        self._lock = threading.Lock()

    def hit(self, keys: tuple[str, ...], now: datetime) -> int | None:
        """Registra un intento para todas las claves. Devuelve los segundos de espera si
        alguna excede su límite (y entonces no registra nada), o `None`."""
        with self._lock:
            worst = 0
            for key in keys:
                events = self._events.setdefault(key, deque())
                while events and now - events[0] >= timedelta(seconds=self._longest):
                    events.popleft()
                for count, seconds in self._limits:
                    window_start = now - timedelta(seconds=seconds)
                    recent = [e for e in events if e > window_start]
                    if len(recent) >= count:
                        wait = recent[-count] + timedelta(seconds=seconds) - now
                        worst = max(worst, int(wait.total_seconds()) + 1)
            if worst:
                return worst
            for key in keys:
                self._events[key].append(now)
            return None

    def reset(self) -> None:
        with self._lock:
            self._events.clear()
