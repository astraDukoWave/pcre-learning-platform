"""Consultas de repasos (`review_schedule`)."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.progress.models import ReviewSchedule


def schedule_of(s: Session, user_id: uuid.UUID) -> list[ReviewSchedule]:
    return list(
        s.scalars(
            select(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id)
            .order_by(ReviewSchedule.due_at, ReviewSchedule.objective_code)
        )
    )
