"""Modelo de repasos (`docs/arquitectura.md` §5.1, progress)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewSchedule(Base):
    __tablename__ = "review_schedule"
    __table_args__ = (
        UniqueConstraint("user_id", "objective_code", name="uq_review_schedule_user_objective"),
        Index("ix_review_schedule_user_due", "user_id", "due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    objective_code: Mapped[str] = mapped_column(String(16))
    stage: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_outcome: Mapped[str] = mapped_column(String(16))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
