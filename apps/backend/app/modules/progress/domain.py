"""Repaso espaciado 1/3/7 (REQ-14), puro y con el tiempo como argumento.

- Un objetivo fallado (primer intento de práctica o repaso) pasa a la etapa 0 y vence a
  las 24 h.
- Un acierto sin ayudas en un repaso vencido avanza: etapa 1 (+3 días), etapa 2 (+7 días)
  y después se queda en 7 días (etapa 3).
- Un fallo reinicia. Un acierto con ayudas no avanza.
- Los vencidos se calculan al pedirlos: sin cron.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Literal, Protocol

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


# -- métricas (REQ-13) -----------------------------------------------------------------------

AUTO_GRADED = frozenset({"choice", "word_completion", "sentence_order", "guided_dialogue"})
METRIC_DAYS = 30


class AttemptLike(Protocol):
    @property
    def attempt_id(self) -> uuid.UUID: ...

    @property
    def item_id(self) -> uuid.UUID: ...

    @property
    def activity_key(self) -> str: ...

    @property
    def fmt(self) -> str: ...

    @property
    def mode(self) -> str: ...

    @property
    def objectives(self) -> tuple[str, ...]: ...

    @property
    def evaluation_status(self) -> str: ...

    @property
    def evaluation_source(self) -> str: ...

    @property
    def score(self) -> float | None: ...

    @property
    def correct(self) -> bool | None: ...

    @property
    def aided(self) -> bool: ...

    @property
    def is_first(self) -> bool: ...

    @property
    def repeated(self) -> bool: ...

    @property
    def local_day(self) -> date: ...

    @property
    def submitted_at(self) -> datetime: ...


class LessonLike(Protocol):
    @property
    def item_id(self) -> uuid.UUID: ...

    @property
    def kind(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def unit_slug(self) -> str | None: ...

    @property
    def position(self) -> int: ...

    @property
    def started(self) -> bool: ...

    @property
    def completed(self) -> bool: ...


class CandidateLike(Protocol):
    @property
    def activity_id(self) -> uuid.UUID: ...

    @property
    def last_answered_at(self) -> datetime | None: ...


def ratio(correct: int, total: int) -> dict[str, int]:
    """Numerador y denominador visibles; con denominador cero la interfaz dice "aún sin
    medición" (nunca 0 %)."""
    return {"correct": correct, "total": total}


def initial_accuracy(attempts: Sequence[AttemptLike], since: datetime) -> dict[str, int]:
    """Primer intento evaluable por actividad corregida automáticamente, en práctica."""
    rows = [
        a
        for a in attempts
        if a.mode == "practice"
        and a.is_first
        and a.fmt in AUTO_GRADED
        and a.evaluation_status == "evaluated"
        and a.submitted_at >= since
    ]
    return ratio(sum(1 for a in rows if a.correct), len(rows))


def delayed_recall(attempts: Sequence[AttemptLike], since: datetime) -> dict[str, int]:
    """Desempeño sin ayudas en el pool `review`; un repaso reutilizado (`repeated`) no
    cuenta como recuperación diferida."""
    rows = [
        a
        for a in attempts
        if a.mode == "review"
        and a.fmt in AUTO_GRADED
        and a.evaluation_status == "evaluated"
        and not a.aided
        and not a.repeated
        and a.submitted_at >= since
    ]
    return ratio(sum(1 for a in rows if a.correct), len(rows))


def production(attempts: Sequence[AttemptLike]) -> dict[str, dict[str, Any]]:
    """Promedio de autoevaluación (0–3) por tipo de producción, etiquetado como tal."""
    out: dict[str, dict[str, Any]] = {}
    for fmt, name in (("short_writing", "writing"), ("recorded_speaking", "speaking")):
        scores = [
            a.score
            for a in attempts
            if a.fmt == fmt
            and a.evaluation_source == "self"
            and a.evaluation_status == "evaluated"
            and a.score is not None
        ]
        out[name] = {
            "average": round(3 * sum(scores) / len(scores), 1) if scores else None,
            "count": len(scores),
            "label": "autoevaluación",
        }
    return out


def to_reinforce(attempts: Sequence[AttemptLike], since: datetime) -> list[dict[str, Any]]:
    """Objetivos con primer intento fallido o repaso fallido en el periodo, con la evidencia
    más reciente."""
    latest: dict[str, AttemptLike] = {}
    for a in attempts:
        failed_first = a.mode == "practice" and a.is_first and a.correct is False
        failed_review = a.mode == "review" and a.correct is False
        if a.submitted_at < since or not (failed_first or failed_review):
            continue
        for code in a.objectives:
            if code not in latest or latest[code].submitted_at <= a.submitted_at:
                latest[code] = a
    return [
        {
            "objective": code,
            "failed_at": a.submitted_at.isoformat(),
            "attempt_id": str(a.attempt_id),
            "item_id": str(a.item_id),
            "activity_key": a.activity_key,
        }
        for code, a in sorted(latest.items())
    ]


def streak(days: set[date], today: date) -> int:
    """Días locales consecutivos con al menos un envío; varios envíos el mismo día cuentan
    una vez. Si hoy aún no hay envío, la racha sigue viva desde ayer."""
    day = today if today in days else today - timedelta(days=1)
    count = 0
    while day in days:
        count += 1
        day -= timedelta(days=1)
    return count


def lesson_advance(lessons: Sequence[LessonLike]) -> dict[str, Any]:
    """Avance: lecciones completadas sobre publicadas, total y por unidad (nunca "% de
    inglés"). Un duplicado no infla: hay una fila de progreso por lección."""
    only = [lesson for lesson in lessons if lesson.kind == "lesson"]
    by_unit: dict[str, list[LessonLike]] = {}
    for lesson in only:
        by_unit.setdefault(lesson.unit_slug or "", []).append(lesson)
    return {
        **ratio(sum(1 for lesson in only if lesson.completed), len(only)),
        "units": [
            {"unit": unit, **ratio(sum(1 for x in rows if x.completed), len(rows))}
            for unit, rows in sorted(by_unit.items())
        ],
    }


def next_lesson(lessons: Sequence[LessonLike]) -> LessonLike | None:
    """ "Continuar": la lección en curso; si no hay, la siguiente recomendada (orden de la
    ruta, sin bloqueos)."""
    started = [x for x in lessons if x.started and not x.completed]
    if started:
        return started[0]
    return next((x for x in lessons if not x.completed), None)


def choose_review(candidates: Sequence[CandidateLike]) -> tuple[CandidateLike, bool] | None:
    """REQ-14: una actividad del pool `review` que el alumno no haya respondido; si no
    queda ninguna, la menos reciente, marcada `repeated`."""
    if not candidates:
        return None
    fresh = [c for c in candidates if c.last_answered_at is None]
    if fresh:
        return fresh[0], False
    oldest = min(candidates, key=lambda c: c.last_answered_at or datetime.min)
    return oldest, True
