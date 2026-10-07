"""Consultas de `insights`. Lee tablas de otros módulos solo para el panel del piloto
(excepción de `repository` en los contratos de import); nunca las escribe."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session

from app.modules.coaching.voice.models import VoiceSession
from app.modules.content.models import ContentItem, ContentReport, ContentRevision
from app.modules.identity.models import User, UserRole
from app.modules.insights.models import ErrorEvent, ProductEvent, UserFeedback
from app.modules.practice.models import AssessmentRun, Attempt, LessonProgress
from app.modules.progress.models import ReviewSchedule
from app.modules.usage.models import AiRun, BudgetPeriod


def add(s: Session, row: ProductEvent | UserFeedback | ErrorEvent) -> None:
    s.add(row)


def purge_errors(s: Session, before: datetime) -> int:
    result = s.execute(delete(ErrorEvent).where(ErrorEvent.occurred_at < before))
    return int(getattr(result, "rowcount", 0) or 0)


def _pilot_students() -> Select[uuid.UUID]:
    """Alumnos del piloto: las cuentas internas y los admins quedan fuera de las métricas."""
    return select(User.id).where(User.role == UserRole.student, User.is_internal.is_(False))


def active_by_day(s: Session, since: date) -> list[tuple[date, int]]:
    rows = s.execute(
        select(Attempt.local_day, func.count(func.distinct(Attempt.user_id)))
        .where(Attempt.user_id.in_(_pilot_students()), Attempt.local_day >= since)
        .group_by(Attempt.local_day)
    )
    return [(day, int(n)) for day, n in rows]


def count_attempts(s: Session, since: datetime, mode: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(Attempt)
        .where(Attempt.user_id.in_(_pilot_students()), Attempt.submitted_at >= since)
    )
    if mode is not None:
        stmt = stmt.where(Attempt.mode == mode)
    return int(s.scalar(stmt) or 0)


def count_lessons_completed(s: Session, since: datetime) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(LessonProgress)
            .where(
                LessonProgress.user_id.in_(_pilot_students()),
                LessonProgress.completed_at >= since,
            )
        )
        or 0
    )


def count_reviews_due(s: Session, now: datetime) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(ReviewSchedule)
            .where(ReviewSchedule.user_id.in_(_pilot_students()), ReviewSchedule.due_at <= now)
        )
        or 0
    )


def count_runs(s: Session, since: datetime, form_kind: str) -> int:
    return int(
        s.scalar(
            select(func.count())
            .select_from(AssessmentRun)
            .where(
                AssessmentRun.user_id.in_(_pilot_students()),
                AssessmentRun.form_kind == form_kind,
                AssessmentRun.status == "submitted",
                AssessmentRun.submitted_at >= since,
            )
        )
        or 0
    )


def lesson_ratings(s: Session, since: datetime) -> list[int]:
    return [
        int(r)
        for r in s.scalars(
            select(UserFeedback.rating).where(
                UserFeedback.user_id.in_(_pilot_students()),
                UserFeedback.context_type == "lesson",
                UserFeedback.rating.is_not(None),
                UserFeedback.created_at >= since,
            )
        )
        if r is not None
    ]


def latest_comments(s: Session, since: datetime, limit: int) -> list[dict[str, Any]]:
    rows = s.execute(
        select(UserFeedback, User.email)
        .join(User, User.id == UserFeedback.user_id)
        .where(
            UserFeedback.user_id.in_(_pilot_students()),
            UserFeedback.message != "",
            UserFeedback.created_at >= since,
        )
        .order_by(UserFeedback.created_at.desc())
        .limit(limit)
    )
    return [_feedback_row(f, email) for f, email in rows]


def all_feedback(s: Session, limit: int) -> list[dict[str, Any]]:
    rows = s.execute(
        select(UserFeedback, User.email, User.is_internal)
        .join(User, User.id == UserFeedback.user_id)
        .order_by(UserFeedback.created_at.desc())
        .limit(limit)
    )
    return [_feedback_row(f, email) | {"internal": internal} for f, email, internal in rows]


def ratings_by_lesson(s: Session) -> list[dict[str, Any]]:
    rows = s.execute(
        select(
            UserFeedback.context_id,
            func.avg(UserFeedback.rating),
            func.count(UserFeedback.rating),
        )
        .where(
            UserFeedback.user_id.in_(_pilot_students()),
            UserFeedback.context_type == "lesson",
            UserFeedback.rating.is_not(None),
        )
        .group_by(UserFeedback.context_id)
    )
    out = []
    for item_id, avg, count in rows:
        title = s.scalar(
            select(ContentRevision.body["title"].astext)
            .join(ContentItem, ContentItem.published_revision_id == ContentRevision.id)
            .where(ContentItem.id == item_id)
        )
        out.append(
            {
                "item_id": str(item_id),
                "title": title or "(retirada)",
                "average": round(float(avg), 2),
                "count": int(count),
            }
        )
    return sorted(out, key=lambda r: r["title"])


def open_reports(s: Session) -> int:
    return int(
        s.scalar(
            select(func.count()).select_from(ContentReport).where(ContentReport.status == "open")
        )
        or 0
    )


def errors_since(s: Session, since: datetime, limit: int) -> tuple[int, list[ErrorEvent]]:
    total = int(
        s.scalar(
            select(func.count()).select_from(ErrorEvent).where(ErrorEvent.occurred_at >= since)
        )
        or 0
    )
    latest = list(
        s.scalars(
            select(ErrorEvent)
            .where(ErrorEvent.occurred_at >= since)
            .order_by(ErrorEvent.occurred_at.desc())
            .limit(limit)
        )
    )
    return total, latest


def _feedback_row(f: UserFeedback, email: str) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "email": email,
        "context_type": f.context_type,
        "context_id": str(f.context_id) if f.context_id else None,
        "rating": f.rating,
        "message": f.message,
        "page": f.page,
        "created_at": f.created_at.isoformat(),
    }


def ai_run_owner(s: Session, run_id: uuid.UUID) -> uuid.UUID | None:
    return s.scalar(
        select(AiRun.user_id).where(
            AiRun.id == run_id, AiRun.purpose.in_(("writing_feedback", "speaking_feedback"))
        )
    )


# -- MVP-02: voz e IA (REQ-07) -------------------------------------------------------------


def voice_end_reasons(s: Session, since: datetime) -> dict[str, int]:
    rows = s.execute(
        select(VoiceSession.end_reason, func.count())
        .where(
            VoiceSession.user_id.in_(_pilot_students()),
            VoiceSession.created_at >= since,
            VoiceSession.ended_at.is_not(None),
        )
        .group_by(VoiceSession.end_reason)
    )
    return {str(reason): int(n) for reason, n in rows}


def voice_seconds_since(s: Session, since: datetime) -> int:
    """Segundos facturables conciliados (las reservas de las sesiones cerradas)."""
    return int(
        s.scalar(
            select(func.coalesce(func.sum(AiRun.observed_units), 0)).where(
                AiRun.user_id.in_(_pilot_students()),
                AiRun.purpose == "voice_session",
                AiRun.status.in_(("succeeded", "unknown")),
                AiRun.created_at >= since,
            )
        )
        or 0
    )


def voice_session_owner(s: Session, session_id: uuid.UUID) -> uuid.UUID | None:
    return s.scalar(select(VoiceSession.user_id).where(VoiceSession.id == session_id))


def voice_ratings(s: Session, since: datetime) -> list[int]:
    return [
        int(r)
        for r in s.scalars(
            select(UserFeedback.rating).where(
                UserFeedback.user_id.in_(_pilot_students()),
                UserFeedback.context_type == "voice",
                UserFeedback.rating.is_not(None),
                UserFeedback.created_at >= since,
            )
        )
        if r is not None
    ]


def voice_transcripts(s: Session, since: datetime) -> list[list[dict[str, Any]]]:
    """Transcripciones guardadas (con consentimiento) para contar turnos disputados; el panel
    nunca muestra su texto."""
    return [
        list(t)
        for t in s.scalars(
            select(VoiceSession.transcript).where(
                VoiceSession.user_id.in_(_pilot_students()),
                VoiceSession.created_at >= since,
                VoiceSession.transcript.is_not(None),
            )
        )
        if t is not None
    ]


def ai_calls_since(s: Session, since: datetime) -> dict[str, int]:
    rows = s.execute(
        select(AiRun.purpose, func.count())
        .where(AiRun.user_id.in_(_pilot_students()), AiRun.created_at >= since)
        .group_by(AiRun.purpose)
    )
    return {str(purpose): int(n) for purpose, n in rows}


def global_budget(s: Session, period: str) -> tuple[int, int, int] | None:
    """Tope, reservado y gastado del presupuesto global del mes (todas las cuentas)."""
    row = s.scalars(
        select(BudgetPeriod).where(BudgetPeriod.scope == "global", BudgetPeriod.period == period)
    ).one_or_none()
    if row is None:
        return None
    return row.limit_microusd, row.reserved_microusd, row.spent_microusd
