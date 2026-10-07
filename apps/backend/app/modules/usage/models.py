"""Modelos de `usage` (`docs/arquitectura.md` §5): presupuestos por periodo y ejecuciones
de IA y voz con su reserva."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TS = DateTime(timezone=True)


class BudgetPeriod(Base):
    """Un presupuesto `global` (`scope_key = 'global'`) o de un alumno (`scope_key` = su id)
    por mes UTC. El tope se copia de la configuración en cada reserva."""

    __tablename__ = "budget_periods"
    __table_args__ = (
        UniqueConstraint("scope", "scope_key", "period", name="uq_budget_periods_scope_period"),
        CheckConstraint("scope IN ('global', 'user')", name="ck_budget_periods_scope"),
        CheckConstraint(
            "(scope = 'global' AND user_id IS NULL) OR (scope = 'user' AND user_id IS NOT NULL)",
            name="ck_budget_periods_user",
        ),
        CheckConstraint(
            "limit_microusd >= 0 AND reserved_microusd >= 0 AND spent_microusd >= 0",
            name="ck_budget_periods_amounts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(8))
    scope_key: Mapped[str] = mapped_column(String(40))
    period: Mapped[str] = mapped_column(String(7))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    limit_microusd: Mapped[int] = mapped_column(BigInteger)
    reserved_microusd: Mapped[int] = mapped_column(BigInteger, default=0)
    spent_microusd: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[datetime] = mapped_column(TS)


class AiRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('writing_feedback', 'speaking_feedback', 'transcription', "
            "'voice_session')",
            name="ck_ai_runs_purpose",
        ),
        CheckConstraint(
            "status IN ('reserved', 'running', 'succeeded', 'failed', 'unknown', 'released')",
            name="ck_ai_runs_status",
        ),
        UniqueConstraint("user_id", "purpose", "idempotency_key", name="uq_ai_runs_idempotency"),
        Index("ix_ai_runs_period_user", "period", "user_id"),
        Index("ix_ai_runs_attempt", "attempt_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(24))
    period: Mapped[str] = mapped_column(String(7))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
    rubric_version: Mapped[str | None] = mapped_column(String(40))
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attempts.id", ondelete="SET NULL")
    )
    voice_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("voice_sessions.id", ondelete="SET NULL", name="fk_ai_runs_voice_session")
    )
    status: Mapped[str] = mapped_column(String(10))
    reserved_microusd: Mapped[int] = mapped_column(BigInteger)
    observed_units: Mapped[int | None] = mapped_column(Integer)
    cost_microusd: Mapped[int | None] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(60))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
