"""Repaso espaciado 1/3/7 (REQ-14), puro y con el tiempo como argumento.

- Un objetivo fallado (primer intento de práctica o repaso) pasa a la etapa 0 y vence a
  las 24 h.
- Un acierto sin ayudas en un repaso vencido avanza: etapa 1 (+3 días), etapa 2 (+7 días)
  y después se queda en 7 días (etapa 3).
- Un fallo reinicia. Un acierto con ayudas no avanza.
- Los vencidos se calculan al pedirlos: sin cron.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

Outcome = Literal["correct", "incorrect"]
AttemptMode = Literal["practice", "review"]
MAX_STAGE = 3


@dataclass(frozen=True)
class ReviewState:
    stage: int
    due_at: datetime
    last_outcome: str


def interval(stage: int, intervals_hours: tuple[int, ...]) -> timedelta:
    index = min(stage, len(intervals_hours) - 1)
    return timedelta(hours=intervals_hours[index])


def next_review_state(
    current: ReviewState | None,
    *,
    outcome: Outcome,
    aided: bool,
    mode: AttemptMode,
    first_attempt: bool,
    now: datetime,
    intervals_hours: tuple[int, ...],
) -> ReviewState | None:
    """Nuevo estado del objetivo tras un intento evaluado, o `None` si no cambia."""
    if mode == "practice":
        # En práctica solo cuenta el primer intento evaluable de cada actividad.
        if not first_attempt or outcome == "correct":
            return None
        return ReviewState(0, now + interval(0, intervals_hours), "incorrect")

    # mode == "review"
    if outcome == "incorrect":
        return ReviewState(0, now + interval(0, intervals_hours), "incorrect")
    if current is None:
        return None
    if now < current.due_at:
        return None  # un repaso adelantado no avanza la etapa
    if aided:
        return ReviewState(
            current.stage, now + interval(current.stage, intervals_hours), "correct_aided"
        )
    stage = min(current.stage + 1, MAX_STAGE)
    return ReviewState(stage, now + interval(stage, intervals_hours), "correct")


def is_due(state: ReviewState, now: datetime) -> bool:
    return state.due_at <= now
