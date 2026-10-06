"""Modelos de práctica (`docs/arquitectura.md` §5.1): inscripción, progreso con revisión
fijada, ayudas servidas, intentos (append-only), idempotencia y corridas de comprobación."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TS = DateTime(timezone=True)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "path_id", name="uq_enrollments_user_path"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    catalog_version_at_enroll: Mapped[int] = mapped_column(Integer)
    enrolled_at: Mapped[datetime] = mapped_column(TS)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_lesson_progress_user_item"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"))
    pinned_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(TS)
    completed_at: Mapped[datetime | None] = mapped_column(TS)


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_user_submitted", "user_id", "submitted_at"),
        Index("ix_attempts_user_activity", "user_id", "activity_id"),
        CheckConstraint("mode IN ('practice', 'review', 'assessment')", name="ck_attempts_mode"),
        CheckConstraint(
            "evaluation_status IN ('evaluated', 'pending', 'not_evaluable', 'failed')",
            name="ck_attempts_evaluation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="RESTRICT"))
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="RESTRICT")
    )
    mode: Mapped[str] = mapped_column(String(12))
    assessment_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessment_runs.id", ondelete="SET NULL", name="fk_attempts_assessment_run")
    )
    revision_of: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attempts.id", ondelete="SET NULL")
    )
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    aids: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict
    )
    evaluation_status: Mapped[str] = mapped_column(String(16))
    evaluation_source: Mapped[str] = mapped_column(String(8))
    score: Mapped[float | None] = mapped_column(Float)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_first: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    repeated: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    submitted_at: Mapped[datetime] = mapped_column(TS)
    local_day: Mapped[date] = mapped_column(Date)


class ServedAid(Base):
    __tablename__ = "served_aids"
    __table_args__ = (
        Index("ix_served_aids_user_activity", "user_id", "activity_id"),
        CheckConstraint(
            "kind IN ('hint', 'support_es', 'transcript', 'example', 'audio_play')",
            name="ck_served_aids_kind",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(16))
    index: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    served_at: Mapped[datetime] = mapped_column(TS)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attempts.id", ondelete="SET NULL")
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "operation", "key", name="uq_idempotency_user_operation_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    operation: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TS)


class AssessmentRun(Base):
    """Corrida de una comprobación (REQ-12) con el orden de ítems fijado al iniciar.

    Diagnóstico inicial: una corrida vigente por alumno (`reset_at` nulo); un admin la
    reinicia y queda en el historial. Checkpoint: se repite y se numera; la primera es la
    comparable."""

    __tablename__ = "assessment_runs"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'submitted')", name="ck_assessment_runs_status"),
        CheckConstraint(
            "form_kind IN ('initial', 'checkpoint', 'final')", name="ck_assessment_runs_form_kind"
        ),
        UniqueConstraint(
            "user_id", "form_item_id", "run_number", name="uq_assessment_runs_user_form_number"
        ),
        Index(
            "uq_assessment_runs_in_progress",
            "user_id",
            "form_item_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
        ),
        Index(
            "uq_assessment_runs_one_diagnostic",
            "user_id",
            "form_item_id",
            unique=True,
            postgresql_where=text("form_kind = 'initial' AND reset_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    form_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_items.id", ondelete="RESTRICT")
    )
    form_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="RESTRICT")
    )
    form_kind: Mapped[str] = mapped_column(String(12))
    run_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))
    item_order: Mapped[list[str]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(TS)
    submitted_at: Mapped[datetime | None] = mapped_column(TS)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reset_at: Mapped[datetime | None] = mapped_column(TS)


class AssessmentAnswer(Base):
    """Respuesta guardada al momento (`PUT`) sin feedback; se corrige al enviar la corrida."""

    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("run_id", "activity_id", name="uq_assessment_answers_run_activity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assessment_runs.id", ondelete="CASCADE"))
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="RESTRICT"))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    audio_failed: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    saved_at: Mapped[datetime] = mapped_column(TS)
