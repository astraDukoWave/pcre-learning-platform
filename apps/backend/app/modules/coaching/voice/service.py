"""Sesiones de voz: creación con reserva y cupo, conexión, cierre con conciliación y barrido
de huérfanas (MVP-02 REQ-05). Solo base de datos y presupuesto; el relay (asíncrono) vive en
`relay.py` y llama a estos métodos fuera del event loop.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AppError, Conflict, NotFound, ValidationFailed
from app.core.logging import user_ref
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.voice import domain, repository
from app.modules.coaching.voice.models import VoiceSession
from app.modules.identity.service import IdentityService
from app.modules.usage.service import UsageService

logger = logging.getLogger("app.coaching.voice")

PURPOSE: Final = "voice_session"
CLOSED = ("ended", "failed", "expired")
# Una reserva de voz abierta más vieja que esto ya no tiene una sesión posible (máx. 330 s).
ORPHAN_RUN_MINUTES = 10


class VoiceBusy(AppError):
    status_code = 503
    code = "voice_busy"
    default_message = "Intenta en unos minutos: hay muchas sesiones de voz abiertas."
    expected = True


class VoiceRejected(Exception):
    """La conexión al WebSocket no procede (sesión ajena, usada, cerrada o vencida)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SessionTicket:
    id: uuid.UUID
    user_id: uuid.UUID
    scenario: dict[str, Any]
    max_seconds: int
    deadline_at: datetime
    save_transcript: bool


class VoiceService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        settings: Settings,
        usage: UsageService,
        identity: IdentityService,
        *,
        agent_model: str | None = None,
    ) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings
        self.usage = usage
        self.identity = identity
        self.agent_model = agent_model

    # -- crear ----------------------------------------------------------------------------

    def create(
        self,
        user_id: uuid.UUID,
        *,
        scenario_id: uuid.UUID,
        idempotency_key: str,
        accept_voice_notice: bool,
        save_transcript: bool,
    ) -> dict[str, Any]:
        self.usage.require("voice")
        self.sweep()
        with self.uow() as s:
            found = repository.published_scenario(s, scenario_id)
            if found is None:
                raise NotFound()
            item, revision = found
            body = dict(revision.body)
        if self.identity.voice_notice(user_id, accept=accept_voice_notice) is None:
            raise ValidationFailed(
                "Acepta el aviso de procesamiento de voz para empezar.",
                code="voice_notice_required",
            )
        same_key = self.usage.run_by_key(user_id, PURPOSE, idempotency_key)
        if same_key is not None:
            return self._replay(user_id, same_key.id, same_key.status, same_key.error_code)
        max_seconds = domain.session_seconds(
            int(body.get("max_seconds", 300)), self.settings.voice_max_session_s
        )
        reservation = self.usage.reserve(
            user_id,
            purpose=PURPOSE,
            amount=domain.cost_microusd(max_seconds, self.settings.voice_price_per_min_microusd),
            idempotency_key=idempotency_key,
            provider="deepgram",
            model=self.agent_model,
            voice_seconds=max_seconds,
        )
        if reservation.existing:  # otra petición con la misma clave llegó primero
            return self._replay(user_id, reservation.run_id, "reserved", None)
        now = self.clock.now()
        session_id = uuid.uuid4()
        with self.uow() as s:
            repository.lock_quota(s)
            if repository.user_live(s, user_id) is not None:
                problem = "session_exists"
            elif repository.live_count(s) >= domain.MAX_LIVE_GLOBAL:
                problem = "voice_busy"
            else:
                problem = None
                repository.add(
                    s,
                    VoiceSession(
                        id=session_id,
                        user_id=user_id,
                        scenario_item_id=item.id,
                        scenario_revision_id=revision.id,
                        status="reserved",
                        max_seconds=max_seconds,
                        save_transcript=save_transcript,
                        created_at=now,
                        deadline_at=domain.deadline_for(now, max_seconds),
                        aids=[],
                        ai_run_id=reservation.run_id,
                    ),
                )
        if problem is not None:
            self.usage.release(reservation.run_id, error_code=problem)
            self._raise(problem)
        self.usage.attach_voice_session(reservation.run_id, session_id)
        logger.info(
            "voice_session_reserved",
            extra={"user_ref": user_ref(user_id, self.settings.log_salt), "seconds": max_seconds},
        )
        return self.view(user_id, session_id)

    def _replay(
        self, user_id: uuid.UUID, run_id: uuid.UUID, status: str, error_code: str | None
    ) -> dict[str, Any]:
        with self.uow() as s:
            session = repository.by_run(s, run_id)
            session_id = session.id if session is not None else None
        if session_id is not None:
            return self.view(user_id, session_id)
        if status == "failed" and error_code in ("session_exists", "voice_busy"):
            self._raise(error_code)
        raise Conflict("La sesión anterior se está creando.", code="voice_session_in_progress")

    @staticmethod
    def _raise(problem: str) -> None:
        if problem == "session_exists":
            raise Conflict("Ya tienes una sesión de voz abierta.", code="voice_session_exists")
        raise VoiceBusy()

    # -- conexión y cierre (los llama el relay) -------------------------------------------

    def claim(self, session_id: uuid.UUID, user_id: uuid.UUID) -> SessionTicket:
        """Una sola conexión por sesión: la propia, `reserved`, sin conectar y a tiempo."""
        now = self.clock.now()
        with self.uow() as s:
            session = repository.get(s, session_id, lock=True)
            if session is None or session.user_id != user_id:
                raise VoiceRejected("not_found")
            if session.status != "reserved" or session.connected_at is not None:
                raise VoiceRejected("in_use")
            if now > domain.connect_by(session.created_at):
                raise VoiceRejected("expired")
            session.connected_at = now
            return SessionTicket(
                id=session.id,
                user_id=session.user_id,
                scenario=repository.revision_body(s, session.scenario_revision_id),
                max_seconds=session.max_seconds,
                deadline_at=session.deadline_at,
                save_transcript=session.save_transcript,
            )

    def mark_active(self, session_id: uuid.UUID) -> datetime | None:
        """`reserved` → `active`. `None` si ya no está `reserved` (un stop o el barrido la
        cerraron mientras se conectaba): el relay no debe conversar."""
        now = self.clock.now()
        with self.uow() as s:
            session = repository.get(s, session_id, lock=True)
            if session is None or session.status != "reserved":
                return None
            session.status = "active"
            session.started_at = now
        return now

    def finish(
        self,
        session_id: uuid.UUID,
        *,
        reason: str,
        transcript: list[dict[str, Any]] | None = None,
        aids: list[dict[str, Any]] | None = None,
        learner_speech_ms: int = 0,
    ) -> dict[str, Any]:
        """Cierra la sesión (idempotente) y concilia: segundos facturables = fin − inicio,
        hasta el máximo. Una sesión que nunca empezó libera la reserva."""
        now = self.clock.now()
        with self.uow() as s:
            session = repository.get(s, session_id, lock=True)
            if session is None:
                raise NotFound()
            if session.status in CLOSED:
                return _summary(session)
            started = session.started_at
            session.status = "ended" if started is not None else "failed"
            session.ended_at = now
            session.end_reason = reason
            session.aids = list(aids or [])
            session.learner_speech_ms = max(0, learner_speech_ms)
            if session.save_transcript and transcript is not None:
                session.transcript = list(transcript)
            run_id = session.ai_run_id
            seconds = min(domain.billable_seconds(started, now), session.max_seconds)
            summary = _summary(session)
            user_id = session.user_id
        if run_id is not None:
            if started is None:
                self.usage.release(run_id, error_code=reason)
            else:
                self.usage.settle(
                    run_id,
                    cost=domain.cost_microusd(seconds, self.settings.voice_price_per_min_microusd),
                    observed_units=seconds,
                )
        logger.info(
            "voice_session_ended",
            extra={
                "user_ref": user_ref(user_id, self.settings.log_salt),
                "end_reason": reason,
                "seconds": seconds,
                "aids": len(aids or []),
            },
        )
        return summary

    def sweep(self) -> int:
        """Huérfanas (REQ-05): `reserved` de más de 2 min → `expired` y se libera; `active`
        más de 60 s pasado el deadline → `expired` con la reserva completa como gasto."""
        now = self.clock.now()
        released: list[uuid.UUID] = []
        spent: list[uuid.UUID] = []
        with self.uow() as s:
            for session in repository.stale(
                s,
                reserved_before=now - timedelta(seconds=domain.ORPHAN_RESERVED_S),
                active_before=now - timedelta(seconds=domain.ORPHAN_ACTIVE_PAST_DEADLINE_S),
            ):
                was_active = session.status == "active"
                session.status = "expired"
                session.ended_at = now
                session.end_reason = "expired"
                if session.ai_run_id is not None:
                    (spent if was_active else released).append(session.ai_run_id)
        # Reservas de voz abiertas sin sesión viva (un fallo entre dos commits): se liberan
        # si la sesión nunca empezó y se cobran completas si empezó.
        for run_id, session_id in self.usage.stale_open_runs(
            PURPOSE, created_before=now - timedelta(minutes=ORPHAN_RUN_MINUTES)
        ):
            if run_id in released or run_id in spent:
                continue  # ya se concilia arriba con su sesión
            with self.uow() as s:
                found = repository.get(s, session_id) if session_id is not None else None
                live = found is not None and found.status in repository.LIVE
                started = found is not None and found.started_at is not None
            if live:
                continue
            (spent if started else released).append(run_id)
        for run_id in released:
            self.usage.release(run_id, error_code="expired")
        for run_id in spent:
            self.usage.expire_as_spent(run_id, error_code="expired")
            logger.warning("voice_session_expired_active")
        return len(released) + len(spent)

    # -- lectura y parada ----------------------------------------------------------------

    def view(self, user_id: uuid.UUID, session_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            session = repository.for_user(s, user_id, session_id)
            if session is None:
                raise NotFound()
            return _summary(session)

    def stop_unconnected(
        self, user_id: uuid.UUID, session_id: uuid.UUID
    ) -> tuple[dict[str, Any], bool]:
        """`POST /stop` sin relay vivo. Una sesión que nunca conectó se cierra y se libera.
        Una ya reclamada por un WebSocket (el relay está arrancando) no se toca aquí:
        devuelve `True` para que el relay la detenga al registrarse."""
        with self.uow() as s:
            session = repository.for_user(s, user_id, session_id)
            if session is None:
                raise NotFound()
            if session.status in CLOSED:
                return _summary(session), False
            if session.connected_at is not None:
                return _summary(session), True
        return self.finish(session_id, reason="user_stop"), False

    def session_alive(self, auth_session_id: uuid.UUID) -> bool:
        return self.identity.session_is_active(auth_session_id)


def _summary(session: VoiceSession) -> dict[str, Any]:
    duration = (
        domain.billable_seconds(session.started_at, session.ended_at)
        if session.ended_at is not None
        else None
    )
    return {
        "id": session.id,
        "scenario_id": session.scenario_item_id,
        "status": session.status,
        "ws_path": f"/ws/voice/{session.id}",
        "max_seconds": session.max_seconds,
        "save_transcript": session.save_transcript,
        "created_at": session.created_at,
        "deadline_at": session.deadline_at,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "end_reason": session.end_reason,
        "duration_s": duration,
        "learner_speech_s": round((session.learner_speech_ms or 0) / 1000, 1),
        "aids": list(session.aids or []),
        "transcript": list(session.transcript) if session.transcript is not None else None,
        "feedback": session.feedback,
    }
