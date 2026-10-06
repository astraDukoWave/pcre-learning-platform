"""Consultas de práctica. Lee tablas de contenido (joins de lectura permitidos, §4) y nunca
las escribe. Todo recurso de alumno se filtra por `user_id`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.content.models import Activity, ContentItem, ContentRevision, LearningPath
from app.modules.practice.models import (
    Attempt,
    Enrollment,
    IdempotencyRecord,
    LessonProgress,
    ServedAid,
)


def claim_idempotency(
    s: Session, *, user_id: uuid.UUID, operation: str, key: str, request_hash: str, now: datetime
) -> IdempotencyRecord | None:
    """Inserta el registro si no existe. Si otra transacción tiene la misma clave en curso,
    PostgreSQL espera a que termine. Devuelve `None` si la clave ya era nuestra."""
    stmt = (
        insert(IdempotencyRecord)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            operation=operation,
            key=key,
            request_hash=request_hash,
            status_code=0,
            created_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_idempotency_user_operation_key")
        .returning(IdempotencyRecord.id)
    )
    inserted = s.execute(stmt).scalar()
    if inserted is not None:
        return None
    existing = s.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    assert existing is not None
    return existing


def store_idempotent_response(
    s: Session, *, user_id: uuid.UUID, operation: str, key: str, status: int, body: dict[str, Any]
) -> None:
    record = s.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )
    assert record is not None
    record.status_code = status
    record.response = body


def activity_with_context(
    s: Session, activity_id: uuid.UUID
) -> tuple[Activity, ContentRevision, ContentItem] | None:
    row = s.execute(
        select(Activity, ContentRevision, ContentItem)
        .join(ContentRevision, ContentRevision.id == Activity.revision_id)
        .join(ContentItem, ContentItem.id == ContentRevision.item_id)
        .where(Activity.id == activity_id)
    ).first()
    return (row[0], row[1], row[2]) if row else None


def item(s: Session, item_id: uuid.UUID) -> ContentItem | None:
    return s.get(ContentItem, item_id)


def revision(s: Session, revision_id: uuid.UUID) -> ContentRevision | None:
    return s.get(ContentRevision, revision_id)


def path(s: Session, path_id: uuid.UUID) -> LearningPath | None:
    return s.get(LearningPath, path_id)


def progress_for(
    s: Session, user_id: uuid.UUID, item_id: uuid.UUID, *, lock: bool = False
) -> LessonProgress | None:
    stmt = select(LessonProgress).where(
        LessonProgress.user_id == user_id, LessonProgress.item_id == item_id
    )
    if lock:
        stmt = stmt.with_for_update()
    return s.scalar(stmt)


def progress_by_item(s: Session, user_id: uuid.UUID) -> dict[uuid.UUID, LessonProgress]:
    rows = s.scalars(select(LessonProgress).where(LessonProgress.user_id == user_id))
    return {r.item_id: r for r in rows}


def ensure_enrollment(s: Session, user_id: uuid.UUID, path: LearningPath, now: datetime) -> None:
    s.execute(
        insert(Enrollment)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            path_id=path.id,
            catalog_version_at_enroll=path.catalog_version,
            enrolled_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_enrollments_user_path")
    )


def activities_of(s: Session, revision_id: uuid.UUID) -> list[Activity]:
    return list(
        s.scalars(
            select(Activity).where(Activity.revision_id == revision_id).order_by(Activity.position)
        )
    )


def unlinked_aids(s: Session, user_id: uuid.UUID, activity_id: uuid.UUID) -> list[ServedAid]:
    return list(
        s.scalars(
            select(ServedAid).where(
                ServedAid.user_id == user_id,
                ServedAid.activity_id == activity_id,
                ServedAid.attempt_id.is_(None),
            )
        )
    )


def prior_attempts_for_key(
    s: Session, user_id: uuid.UUID, item_id: uuid.UUID, activity_key: str
) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(Attempt)
            .join(Activity, Activity.id == Attempt.activity_id)
            .join(ContentRevision, ContentRevision.id == Activity.revision_id)
            .where(
                Attempt.user_id == user_id,
                ContentRevision.item_id == item_id,
                Activity.activity_key == activity_key,
            )
        )
        or 0
    )


def attempted_activity_ids(
    s: Session, user_id: uuid.UUID, revision_id: uuid.UUID
) -> set[uuid.UUID]:
    return set(
        s.scalars(
            select(Attempt.activity_id).where(
                Attempt.user_id == user_id, Attempt.revision_id == revision_id
            )
        )
    )


def last_attempts_by_key(s: Session, user_id: uuid.UUID, item_id: uuid.UUID) -> dict[str, Attempt]:
    """Último intento del alumno por clave de actividad en cualquier revisión del ítem."""
    rows = s.execute(
        select(Activity.activity_key, Attempt)
        .join(Activity, Activity.id == Attempt.activity_id)
        .join(ContentRevision, ContentRevision.id == Activity.revision_id)
        .where(Attempt.user_id == user_id, ContentRevision.item_id == item_id)
        .order_by(Attempt.submitted_at)
    )
    out: dict[str, Attempt] = {}
    for key, attempt in rows:
        out[key] = attempt
    return out


def attempt_for_user(s: Session, user_id: uuid.UUID, attempt_id: uuid.UUID) -> Attempt | None:
    return s.scalar(select(Attempt).where(Attempt.id == attempt_id, Attempt.user_id == user_id))


def recent_attempts(
    s: Session, user_id: uuid.UUID, limit: int, before: datetime | None
) -> list[Attempt]:
    stmt = select(Attempt).where(Attempt.user_id == user_id)
    if before is not None:
        stmt = stmt.where(Attempt.submitted_at < before)
    return list(s.scalars(stmt.order_by(Attempt.submitted_at.desc()).limit(limit)))
