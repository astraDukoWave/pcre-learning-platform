"""Modelos de `insights` (`docs/arquitectura.md` §5.1): feedback del producto, eventos de
producto (lista cerrada de REQ-16) y errores del servidor (5xx, retención de 30 días)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TS = DateTime(timezone=True)


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        CheckConstraint(
            "context_type IN ('lesson', 'general', 'voice', 'ai_observation')",
            name="ck_user_feedback_context",
        ),
        CheckConstraint(
            "rating IS NULL OR (rating BETWEEN 0 AND 5)", name="ck_user_feedback_rating"
        ),
        CheckConstraint("char_length(message) <= 1000", name="ck_user_feedback_message"),
        Index("ix_user_feedback_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    context_type: Mapped[str] = mapped_column(String(16))
    context_id: Mapped[uuid.UUID | None] = mapped_column()
    rating: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, server_default=text("''"), default="")
    page: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(TS)


class ProductEvent(Base):
    __tablename__ = "product_events"
    __table_args__ = (Index("ix_product_events_name_occurred", "name", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(40))
    props: Mapped[dict[str, Any]] = mapped_column(
        JSONB, server_default=text("'{}'::jsonb"), default=dict
    )
    occurred_at: Mapped[datetime] = mapped_column(TS)


class ErrorEvent(Base):
    __tablename__ = "error_events"
    __table_args__ = (Index("ix_error_events_occurred", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_id: Mapped[str] = mapped_column(String(64))
    route: Mapped[str] = mapped_column(String(200))
    status_code: Mapped[int] = mapped_column(Integer)
    error_code: Mapped[str] = mapped_column(String(64))
    exception_type: Mapped[str | None] = mapped_column(String(120))
    occurred_at: Mapped[datetime] = mapped_column(TS)
