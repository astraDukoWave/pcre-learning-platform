"""Modelo de las sesiones de voz (`docs/arquitectura.md` §5, MVP-02 REQ-05)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TS = DateTime(timezone=True)


class VoiceSession(Base):
    """Una conversación con el coach de voz. `transcript` y `feedback` solo con el
    consentimiento de la sesión (`save_transcript`); sin él quedan duración y ayudas."""

    __tablename__ = "voice_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('reserved', 'active', 'ended', 'failed', 'expired')",
            name="ck_voice_sessions_status",
        ),
        Index("ix_voice_sessions_user", "user_id", "created_at"),
        Index(
            "ux_voice_sessions_user_live",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('reserved', 'active')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scenario_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_items.id", ondelete="RESTRICT")
    )
    scenario_revision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("content_revisions.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(10))
    max_seconds: Mapped[int] = mapped_column(Integer)
    save_transcript: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(TS)
    deadline_at: Mapped[datetime] = mapped_column(TS)
    connected_at: Mapped[datetime | None] = mapped_column(TS)
    started_at: Mapped[datetime | None] = mapped_column(TS)
    ended_at: Mapped[datetime | None] = mapped_column(TS)
    end_reason: Mapped[str | None] = mapped_column(String(20))
    aids: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    transcript: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_runs.id", ondelete="SET NULL")
    )
