"""Consultas de `usage`. Lee `users` (email del admin) por la excepción de `repository`."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modules.identity.models import User
from app.modules.usage.models import AiRun, BudgetPeriod

GLOBAL_KEY = "global"


def lock_budget(
    s: Session,
    *,
    scope: str,
    period: str,
    limit: int,
    now: datetime,
    user_id: uuid.UUID | None = None,
) -> BudgetPeriod:
    """Crea la fila del periodo si falta y la bloquea con `SELECT … FOR UPDATE`. El tope se
    actualiza al configurado: un cambio de config var aplica desde la siguiente reserva."""
    key = str(user_id) if user_id is not None else GLOBAL_KEY
    s.execute(
        insert(BudgetPeriod)
        .values(
            id=uuid.uuid4(),
            scope=scope,
            scope_key=key,
            period=period,
            user_id=user_id,
            limit_microusd=limit,
            reserved_microusd=0,
            spent_microusd=0,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_budget_periods_scope_period")
    )
    row = s.scalars(
        select(BudgetPeriod)
        .where(
            BudgetPeriod.scope == scope,
            BudgetPeriod.scope_key == key,
            BudgetPeriod.period == period,
        )
        .with_for_update()
    ).one()
    row.limit_microusd = limit
    return row


def budget(
    s: Session, *, scope: str, period: str, user_id: uuid.UUID | None = None
) -> BudgetPeriod | None:
    key = str(user_id) if user_id is not None else GLOBAL_KEY
    return s.scalars(
        select(BudgetPeriod).where(
            BudgetPeriod.scope == scope,
            BudgetPeriod.scope_key == key,
            BudgetPeriod.period == period,
        )
    ).one_or_none()


def add_run(s: Session, run: AiRun) -> None:
    s.add(run)


def run_by_key(s: Session, user_id: uuid.UUID, purpose: str, key: str) -> AiRun | None:
    return s.scalars(
        select(AiRun).where(
            AiRun.user_id == user_id, AiRun.purpose == purpose, AiRun.idempotency_key == key
        )
    ).one_or_none()


def run_for_update(s: Session, run_id: uuid.UUID) -> AiRun | None:
    return s.scalars(select(AiRun).where(AiRun.id == run_id).with_for_update()).one_or_none()


def voice_seconds(s: Session, user_id: uuid.UUID, period: str) -> int:
    """Segundos de voz comprometidos por el alumno en el periodo: los observados de las
    sesiones cerradas y la reserva completa (300 s) de las abiertas o desconocidas."""
    rows = s.execute(
        select(AiRun.status, AiRun.observed_units).where(
            AiRun.user_id == user_id,
            AiRun.period == period,
            AiRun.purpose == "voice_session",
            AiRun.status.not_in(("failed", "released")),
        )
    )
    return sum(int(units or 0) for _, units in rows)


def usage_by_user(s: Session, period: str) -> list[dict[str, Any]]:
    """Por alumno: llamadas por propósito, segundos de voz, reservado, gastado y email."""
    runs = s.execute(
        select(
            AiRun.user_id,
            func.count().label("calls"),
            func.count().filter(AiRun.purpose == "voice_session").label("voice_sessions"),
            func.coalesce(
                func.sum(AiRun.observed_units).filter(AiRun.purpose == "voice_session"), 0
            ).label("voice_seconds"),
            func.count().filter(AiRun.status == "unknown").label("unknown"),
        )
        .where(AiRun.period == period)
        .group_by(AiRun.user_id)
    ).all()
    budgets = {
        b.user_id: b
        for b in s.scalars(
            select(BudgetPeriod).where(BudgetPeriod.scope == "user", BudgetPeriod.period == period)
        )
    }
    ids = {r.user_id for r in runs} | {uid for uid in budgets if uid is not None}
    emails = {
        uid: email for uid, email in s.execute(select(User.id, User.email).where(User.id.in_(ids)))
    }
    by_user = {r.user_id: r for r in runs}
    out = []
    for uid in sorted(ids, key=lambda u: emails.get(u, "")):
        r = by_user.get(uid)
        b = budgets.get(uid)
        out.append(
            {
                "user_id": uid,
                "email": emails.get(uid, ""),
                "calls": int(r.calls) if r else 0,
                "voice_sessions": int(r.voice_sessions) if r else 0,
                "voice_seconds": int(r.voice_seconds) if r else 0,
                "unknown_runs": int(r.unknown) if r else 0,
                "limit_microusd": b.limit_microusd if b else None,
                "reserved_microusd": b.reserved_microusd if b else 0,
                "spent_microusd": b.spent_microusd if b else 0,
            }
        )
    return out


def runs_by_purpose(s: Session, period: str) -> dict[str, int]:
    rows = s.execute(
        select(AiRun.purpose, func.count()).where(AiRun.period == period).group_by(AiRun.purpose)
    )
    return {purpose: int(n) for purpose, n in rows}
