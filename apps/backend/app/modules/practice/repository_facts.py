"""Consultas de solo lectura para `progress` (métricas, repasos y "Continuar"). Las expone
`service_facts.py`: `progress` no lee tablas de otros módulos (import-linter, regla 4)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import any_, func, literal, select
from sqlalchemy.orm import Session

from app.modules.content.models import Activity, ContentItem, ContentRevision
from app.modules.practice.models import AssessmentRun, Attempt, LessonProgress, ServedAid


@dataclass(frozen=True)
class AttemptFact:
    attempt_id: uuid.UUID
    item_id: uuid.UUID
    activity_key: str
    fmt: str
    mode: str
    objectives: tuple[str, ...]
    evaluation_status: str
    evaluation_source: str
    score: float | None
    correct: bool | None
    aided: bool
    is_first: bool
    repeated: bool
    local_day: date
    submitted_at: datetime


@dataclass(frozen=True)
class LessonFact:
    item_id: uuid.UUID
    kind: str
    title: str
    unit_slug: str | None
    position: int
    started: bool
    completed: bool


@dataclass(frozen=True)
class ReviewCandidate:
    activity_id: uuid.UUID
    activity_key: str
    item_id: uuid.UUID
    revision_id: uuid.UUID
    last_answered_at: datetime | None


def attempts(s: Session, user_id: uuid.UUID) -> list[AttemptFact]:
    rows = s.execute(
        select(Attempt, Activity, ContentRevision.item_id)
        .join(Activity, Activity.id == Attempt.activity_id)
        .join(ContentRevision, ContentRevision.id == Activity.revision_id)
        .where(Attempt.user_id == user_id)
        .order_by(Attempt.submitted_at)
    )
    return [
        AttemptFact(
            attempt_id=a.id,
            item_id=item_id,
            activity_key=act.activity_key,
            fmt=act.format,
            mode=a.mode,
            objectives=tuple(act.objective_codes),
            evaluation_status=a.evaluation_status,
            evaluation_source=a.evaluation_source,
            score=a.score,
            correct=a.correct,
            aided=bool(a.aids.get("kinds")),
            is_first=a.is_first,
            repeated=a.repeated,
            local_day=a.local_day,
            submitted_at=a.submitted_at,
        )
        for a, act, item_id in rows
    ]


def aid_counts(s: Session, user_id: uuid.UUID, since: datetime) -> dict[str, int]:
    rows = s.execute(
        select(ServedAid.kind, func.count())
        .where(ServedAid.user_id == user_id, ServedAid.served_at >= since)
        .group_by(ServedAid.kind)
    )
    return {kind: int(n) for kind, n in rows}


def lessons(s: Session, user_id: uuid.UUID, path_id: uuid.UUID) -> list[LessonFact]:
    """Lecciones y escenarios publicados de la ruta, con el estado del alumno. El título,
    la unidad y la posición salen de la revisión publicada (lo que ve el alumno)."""
    progress = {
        p.item_id: p
        for p in s.scalars(select(LessonProgress).where(LessonProgress.user_id == user_id))
    }
    rows = s.execute(
        select(ContentItem, ContentRevision)
        .join(ContentRevision, ContentRevision.id == ContentItem.published_revision_id)
        .where(ContentItem.path_id == path_id, ContentItem.kind.in_(("lesson", "scenario")))
    )
    out = []
    for item, rev in rows:
        p = progress.get(item.id)
        out.append(
            LessonFact(
                item_id=item.id,
                kind=item.kind,
                title=rev.body["title"],
                unit_slug=rev.body.get("unit"),
                position=int(rev.body.get("position", 0)),
                started=p is not None,
                completed=bool(p and p.completed_at),
            )
        )
    return sorted(out, key=lambda f: (f.unit_slug or "", f.position))


def diagnostic_pending(s: Session, user_id: uuid.UUID, path_id: uuid.UUID) -> uuid.UUID | None:
    """Id del diagnóstico publicado si el alumno no tiene una corrida enviada vigente."""
    forms = s.execute(
        select(ContentItem.id, ContentRevision.body)
        .join(ContentRevision, ContentRevision.id == ContentItem.published_revision_id)
        .where(ContentItem.path_id == path_id, ContentItem.kind == "assessment_form")
    )
    for form_id, body in forms:
        if body.get("form_kind") != "initial":
            continue
        done = s.scalar(
            select(func.count())
            .select_from(AssessmentRun)
            .where(
                AssessmentRun.user_id == user_id,
                AssessmentRun.form_item_id == form_id,
                AssessmentRun.status == "submitted",
                AssessmentRun.reset_at.is_(None),
            )
        )
        return None if done else form_id
    return None


def review_candidates(
    s: Session, user_id: uuid.UUID, path_id: uuid.UUID, objective: str
) -> list[ReviewCandidate]:
    """Actividades del pool `review` del objetivo en revisiones publicadas, con la última
    vez que el alumno respondió esa clave de actividad (en cualquier revisión del ítem)."""
    rows = s.execute(
        select(Activity, ContentItem.id)
        .join(ContentRevision, ContentRevision.id == Activity.revision_id)
        .join(ContentItem, ContentItem.published_revision_id == ContentRevision.id)
        .where(
            ContentItem.path_id == path_id,
            Activity.pool == "review",
            literal(objective) == any_(Activity.objective_codes),
        )
        .order_by(ContentItem.position, Activity.position)
    )
    last = dict(
        s.execute(
            select(
                func.concat(ContentRevision.item_id, ":", Activity.activity_key),
                func.max(Attempt.submitted_at),
            )
            .join(Activity, Activity.id == Attempt.activity_id)
            .join(ContentRevision, ContentRevision.id == Activity.revision_id)
            .where(Attempt.user_id == user_id)
            .group_by(ContentRevision.item_id, Activity.activity_key)
        ).all()
    )
    return [
        ReviewCandidate(
            activity_id=act.id,
            activity_key=act.activity_key,
            item_id=item_id,
            revision_id=act.revision_id,
            last_answered_at=last.get(f"{item_id}:{act.activity_key}"),
        )
        for act, item_id in rows
    ]
