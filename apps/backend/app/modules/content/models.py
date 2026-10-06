"""Modelos de contenido (`docs/arquitectura.md` §5.1, ADR-03 y ADR-08).

Las columnas editoriales que nombran a una persona del equipo (`approved_by`,
`decided_by`, `created_by` de hallazgos) no son FK a `users`: la bitácora editorial es
un registro de auditoría y no se borra con la cuenta de quien decidió.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TS = DateTime(timezone=True)


class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    exam_code: Mapped[str] = mapped_column(String(40))
    exam_format_version: Mapped[str] = mapped_column(String(20))
    level_from: Mapped[str] = mapped_column(String(4))
    level_to: Mapped[str] = mapped_column(String(4))
    title: Mapped[str] = mapped_column(String(200))
    label: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(
        String(12), server_default=text("'active'"), default="active"
    )
    catalog_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), onupdate=func.now())


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("path_id", "slug", name="uq_units_path_slug"),
        UniqueConstraint("path_id", "position", name="uq_units_path_position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        UniqueConstraint("path_id", "slug", name="uq_content_items_path_slug"),
        CheckConstraint(
            "kind IN ('lesson', 'assessment_form', 'scenario')", name="ck_content_items_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))
    path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("units.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(80))
    position: Mapped[int] = mapped_column(Integer)
    skill: Mapped[str | None] = mapped_column(String(12))
    form_kind: Mapped[str | None] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(200))
    published_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "content_revisions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_content_items_published_revision",
        )
    )
    created_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TS, server_default=func.now(), onupdate=func.now())


class ContentRevision(Base):
    __tablename__ = "content_revisions"
    __table_args__ = (
        UniqueConstraint("item_id", "version", name="uq_content_revisions_item_version"),
        UniqueConstraint("item_id", "content_hash", name="uq_content_revisions_item_hash"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'published', 'superseded', 'withdrawn')",
            name="ck_content_revisions_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_path: Mapped[str] = mapped_column(String(300))
    source_commit: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(12), server_default=text("'draft'"), default="draft")
    file_status: Mapped[str] = mapped_column(String(20))
    lint_errors: Mapped[int] = mapped_column(Integer, server_default=text("0"), default=0)
    lint_warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    audio_pending: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column()
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    approved_hash: Mapped[str | None] = mapped_column(String(64))
    published_at: Mapped[datetime | None] = mapped_column(TS)
    withdrawn_at: Mapped[datetime | None] = mapped_column(TS)
    withdraw_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        UniqueConstraint("revision_id", "activity_key", name="uq_activities_revision_key"),
        Index("ix_activities_activity_key", "activity_key"),
        CheckConstraint("pool IN ('practice', 'review', 'assessment')", name="ck_activities_pool"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE")
    )
    activity_key: Mapped[str] = mapped_column(String(90))
    position: Mapped[int] = mapped_column(Integer)
    format: Mapped[str] = mapped_column(String(24))
    task_family: Mapped[str] = mapped_column(String(40))
    pool: Mapped[str] = mapped_column(String(12))
    objective_codes: Mapped[list[str]] = mapped_column(ARRAY(String(16)))
    prompt: Mapped[dict[str, Any]] = mapped_column(JSONB)
    stimulus: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    options: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    hints: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    support_es: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)
    example: Mapped[str | None] = mapped_column(Text)
    # Privados: solo después de enviar (práctica) o de cerrar la comprobación.
    solution: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(Text)
    rubric: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(60), unique=True)
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(120))
    accessed_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12))


class RevisionSource(Base):
    __tablename__ = "revision_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    claim: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))


class ReviewFinding(Base):
    __tablename__ = "review_findings"
    __table_args__ = (
        CheckConstraint("severity IN ('material', 'minor')", name="ck_review_findings_severity"),
        CheckConstraint(
            "status IN ('open', 'resolved', 'wont_fix')", name="ck_review_findings_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str] = mapped_column(String(80))
    created_by: Mapped[uuid.UUID | None] = mapped_column()
    category: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), server_default=text("'open'"), default="open")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)


class EditorialDecision(Base):
    __tablename__ = "editorial_decisions"
    __table_args__ = (
        CheckConstraint(
            "action IN ('approve', 'publish', 'withdraw', 'request_changes')",
            name="ck_editorial_decisions_action",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(20))
    decided_by: Mapped[uuid.UUID] = mapped_column()
    content_hash: Mapped[str] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS)


class ContentReport(Base):
    __tablename__ = "content_reports"
    __table_args__ = (
        CheckConstraint("char_length(message) <= 1000", name="ck_content_reports_message"),
        CheckConstraint(
            "status IN ('open', 'triaged', 'resolved', 'wont_fix')",
            name="ck_content_reports_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="CASCADE")
    )
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE")
    )
    attempt_id: Mapped[uuid.UUID | None] = mapped_column()
    category: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(Text, server_default=text("''"), default="")
    page: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), server_default=text("'open'"), default="open")
    triage_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TS)
