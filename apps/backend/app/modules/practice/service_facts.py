"""Hechos de práctica de solo lectura para `progress` (métricas, repasos y "Continuar").

`progress` pide aquí datos planos y aplica sus reglas en `progress/domain.py`. Este módulo
no importa `progress`, así no hay ciclo con `practice/service.py`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.practice import repository
from app.modules.practice.repository_facts import (
    AttemptFact,
    LessonFact,
    ReviewCandidate,
    aid_counts,
    attempts,
    diagnostic_pending,
    lessons,
    review_candidates,
)

__all__ = [
    "AttemptFact",
    "LessonFact",
    "ReviewCandidate",
    "aid_counts",
    "attempts",
    "current_path_id",
    "diagnostic_pending",
    "lessons",
    "review_candidates",
]


def current_path_id(s: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    """La ruta inscrita del alumno; si aún no se inscribió, la primera ruta activa."""
    return repository.enrolled_or_first_path(s, user_id)
