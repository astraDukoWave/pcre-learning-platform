"""Casos de uso de progreso. `record_outcome` participa en la transacción del intento
(REQ-14: los repasos se actualizan en la misma transacción)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.progress import domain
from app.modules.progress.models import ReviewSchedule


def record_outcome(
    s: Session,
    *,
    user_id: uuid.UUID,
    objectives: list[str],
    outcome: domain.Outcome,
    aided: bool,
    mode: domain.AttemptMode,
    first_attempt: bool,
    now: datetime,
    intervals_hours: tuple[int, ...],
) -> list[str]:
    """Aplica la regla 1/3/7 a cada objetivo del intento. Devuelve los objetivos cuyo
    repaso cambió."""
    changed = []
    for code in objectives:
        row = s.scalar(
            select(ReviewSchedule)
            .where(ReviewSchedule.user_id == user_id, ReviewSchedule.objective_code == code)
            .with_for_update()
        )
        current = (
            domain.ReviewState(row.stage, row.due_at, row.last_outcome) if row is not None else None
        )
        nxt = domain.next_review_state(
            current,
            outcome=outcome,
            aided=aided,
            mode=mode,
            first_attempt=first_attempt,
            now=now,
            intervals_hours=intervals_hours,
        )
        if nxt is None:
            continue
        if row is None:
            s.add(
                ReviewSchedule(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    objective_code=code,
                    stage=nxt.stage,
                    due_at=nxt.due_at,
                    last_outcome=nxt.last_outcome,
                    updated_at=now,
                )
            )
        else:
            row.stage, row.due_at, row.last_outcome, row.updated_at = (
                nxt.stage,
                nxt.due_at,
                nxt.last_outcome,
                now,
            )
        changed.append(code)
    return changed
