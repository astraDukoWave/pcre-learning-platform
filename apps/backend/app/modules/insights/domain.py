"""Reglas de `insights`, puras: lista cerrada de eventos (REQ-16), propiedades que solo
llevan ids y enumerados, y el resumen del panel del piloto (REQ-15)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Any

EVENT_NAMES = frozenset(
    {
        "invitation_accepted",
        "login",
        "diagnostic_started",
        "diagnostic_completed",
        "lesson_started",
        "lesson_completed",
        "attempt_submitted",
        "aid_used",
        "feedback_viewed",
        "review_completed",
        "checkpoint_completed",
        "content_reported",
        "feedback_submitted",
    }
)
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
ERROR_RETENTION_DAYS = 30
PANEL_WINDOWS = (7, 28)


class InvalidEvent(ValueError):
    """Un evento fuera de la lista cerrada o con texto libre en sus propiedades."""


def clean_props(name: str, props: dict[str, Any]) -> dict[str, Any]:
    """Valida el evento: nombre de la lista cerrada y propiedades con ids, enumerados,
    números o booleanos. Nunca texto del alumno (REQ-16)."""
    if name not in EVENT_NAMES:
        raise InvalidEvent(f"evento fuera de la lista cerrada: {name}")
    out: dict[str, Any] = {}
    for key, value in props.items():
        if not _TOKEN.match(key):
            raise InvalidEvent(f"clave inválida: {key}")
        if isinstance(value, bool | int) or (isinstance(value, str) and _TOKEN.match(value)):
            out[key] = value
        elif value is None:
            continue
        else:
            raise InvalidEvent(f"{name}.{key}: solo ids, enumerados, números o booleanos")
    return out


def active_days(rows: Sequence[tuple[date, int]], since: date, until: date) -> list[dict[str, Any]]:
    """Alumnos activos por día (ya sin cuentas internas), con los días sin actividad en 0."""
    by_day = dict(rows)
    out = []
    day = since
    while day <= until:
        out.append({"day": day.isoformat(), "students": by_day.get(day, 0)})
        day += timedelta(days=1)
    return out


def average(values: Sequence[int]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def window_start(now: datetime, days: int) -> datetime:
    return now - timedelta(days=days)
