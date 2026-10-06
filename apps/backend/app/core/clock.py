"""Reloj inyectable: el dominio nunca llama a `datetime.now()` directamente."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class FakeClock:
    """Reloj controlable para pruebas y para `POST /api/test/clock` (solo `APP_ENV=test`)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 10, 5, 15, 0, tzinfo=UTC)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def set(self, value: datetime) -> None:
        if value.tzinfo is None:
            raise ValueError("el reloj solo acepta fechas con zona horaria")
        with self._lock:
            self._now = value.astimezone(UTC)

    def advance(self, delta: timedelta) -> datetime:
        with self._lock:
            self._now = self._now + delta
            return self._now


class OffsetClock:
    """Reloj del sistema desplazado: lo usa el E2E para "mañana" sin congelar el tiempo."""

    def __init__(self) -> None:
        self._offset = timedelta(0)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return datetime.now(UTC) + self._offset

    def advance(self, delta: timedelta) -> datetime:
        with self._lock:
            self._offset += delta
            return datetime.now(UTC) + self._offset

    def reset(self) -> None:
        with self._lock:
            self._offset = timedelta(0)
