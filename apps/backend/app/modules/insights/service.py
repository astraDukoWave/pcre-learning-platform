"""Casos de uso de `insights`: eventos de producto (REQ-16), feedback del producto y panel
del piloto (REQ-15), errores del servidor (ADR-14).

`emit` corre dentro de la transacción del caso de uso que lo produce: si el intento se
revierte, su evento también.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.errors import NotFound
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.voice import domain as voice_domain
from app.modules.insights import domain, repository
from app.modules.insights.models import ErrorEvent, ProductEvent, UserFeedback

logger = logging.getLogger("app.insights")


def emit(s: Session, user_id: uuid.UUID, name: str, now: datetime, **props: Any) -> None:
    """Registra un evento de la lista cerrada con propiedades de solo ids y enumerados."""
    repository.add(
        s,
        ProductEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
            props=domain.clean_props(name, props),
            occurred_at=now,
        ),
    )


class InsightsService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self.uow = uow
        self.clock = clock

    # -- alumno -------------------------------------------------------------------------

    def submit_feedback(
        self,
        user_id: uuid.UUID,
        *,
        context_type: str,
        context_id: uuid.UUID | None,
        rating: int | None,
        message: str,
        page: str | None,
        observation: int | None = None,
    ) -> uuid.UUID:
        now = self.clock.now()
        feedback_id = uuid.uuid4()
        with self.uow() as s:
            if context_type == "ai_observation":
                # Solo sobre un feedback propio; ajeno o inexistente → 404 (EDGE-06).
                if context_id is None or repository.ai_run_owner(s, context_id) != user_id:
                    raise NotFound()
                page = f"observation:{observation}"
            if context_type == "voice" and (
                context_id is None or repository.voice_session_owner(s, context_id) != user_id
            ):
                raise NotFound()  # sesión de voz ajena o inexistente
            repository.add(
                s,
                UserFeedback(
                    id=feedback_id,
                    user_id=user_id,
                    context_type=context_type,
                    context_id=context_id,
                    rating=rating,
                    message=message.strip(),
                    page=page,
                    created_at=now,
                ),
            )
            emit(s, user_id, "feedback_submitted", now, context=context_type)
        return feedback_id

    # -- panel del piloto ---------------------------------------------------------------

    def pilot_summary(self, days: int) -> dict[str, Any]:
        now = self.clock.now()
        since = domain.window_start(now, days)
        with self.uow() as s:
            ratings = repository.lesson_ratings(s, since)
            errors_total, errors = repository.errors_since(s, since, 10)
            return {
                "days": days,
                "internal_excluded": True,
                "active_by_day": domain.active_days(
                    repository.active_by_day(s, since.date()), since.date(), now.date()
                ),
                "attempts": repository.count_attempts(s, since),
                "lessons_completed": repository.count_lessons_completed(s, since),
                "reviews_done": repository.count_attempts(s, since, mode="review"),
                "reviews_due": repository.count_reviews_due(s, now),
                "diagnostics": repository.count_runs(s, since, "initial"),
                "checkpoints": repository.count_runs(s, since, "checkpoint"),
                "average_rating": domain.average(ratings),
                "ratings": len(ratings),
                "latest_comments": repository.latest_comments(s, since, 10),
                "open_reports": repository.open_reports(s),
                "server_errors": errors_total,
                "latest_errors": [_error_row(e) for e in errors],
                "voice_ai": self._voice_ai(s, since, now),
            }

    def _voice_ai(self, s: Any, since: datetime, now: datetime) -> dict[str, Any]:
        """MVP-02 REQ-07: minutos de voz, sesiones, motivos de cierre, llamadas de IA y costo
        del mes frente al presupuesto global."""
        reasons = repository.voice_end_reasons(s, since)
        ratings = repository.voice_ratings(s, since)
        budget = repository.global_budget(s, now.strftime("%Y-%m"))
        limit, reserved, spent = budget if budget is not None else (None, 0, 0)
        return {
            "voice_minutes": round(repository.voice_seconds_since(s, since) / 60, 1),
            "voice_sessions": sum(reasons.values()),
            "end_reasons": reasons,
            "ai_calls": repository.ai_calls_since(s, since),
            "month": now.strftime("%Y-%m"),
            "month_spent_microusd": spent,
            "month_reserved_microusd": reserved,
            "month_limit_microusd": limit,
            "disputed_turns": sum(
                voice_domain.disputed_turns(t) for t in repository.voice_transcripts(s, since)
            ),
            "voice_rating_average": domain.average(ratings),
            "voice_ratings": len(ratings),
        }

    def feedback_overview(self) -> dict[str, Any]:
        with self.uow() as s:
            return {
                "by_lesson": repository.ratings_by_lesson(s),
                "latest": repository.all_feedback(s, 100),
            }

    def errors(self, days: int) -> list[dict[str, Any]]:
        with self.uow() as s:
            _, rows = repository.errors_since(s, domain.window_start(self.clock.now(), days), 200)
            return [_error_row(e) for e in rows]

    # -- errores del servidor -----------------------------------------------------------

    def record_error(
        self,
        *,
        request_id: str,
        route: str,
        status_code: int,
        error_code: str,
        exception_type: str | None,
    ) -> None:
        """Registra un 5xx en su propia transacción; si la base no responde, solo se
        registra en el log (no hay que convertir un error en dos)."""
        try:
            with self.uow() as s:
                repository.add(
                    s,
                    ErrorEvent(
                        id=uuid.uuid4(),
                        request_id=request_id[:64],
                        route=route[:200],
                        status_code=status_code,
                        error_code=error_code[:64],
                        exception_type=(exception_type or None) and exception_type[:120],
                        occurred_at=self.clock.now(),
                    ),
                )
        except Exception:
            logger.warning("error_event_not_recorded", extra={"route": route[:200]})

    def purge_old_errors(self) -> int:
        """Retención de 30 días: se limpia al arrancar."""
        before = self.clock.now() - timedelta(days=domain.ERROR_RETENTION_DAYS)
        with self.uow() as s:
            return repository.purge_errors(s, before)


def _error_row(e: ErrorEvent) -> dict[str, Any]:
    return {
        "request_id": e.request_id,
        "route": e.route,
        "status_code": e.status_code,
        "error_code": e.error_code,
        "exception_type": e.exception_type,
        "occurred_at": e.occurred_at.isoformat(),
    }
