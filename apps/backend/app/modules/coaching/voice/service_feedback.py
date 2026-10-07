"""Feedback final de una sesión de voz (MVP-02 REQ-05) y turnos disputados (AC-13).

Solo con el consentimiento de la sesión y al menos `VOICE_MIN_LEARNER_SPEECH_S` (30 s) de voz
del alumno: sus turnos (sin las ayudas) se evalúan con la rúbrica del escenario, hasta dos
observaciones con evidencia literal. Mismas reglas que REQ-02: reserva antes de llamar, la
misma clave devuelve lo mismo, solo se reintenta tras `failed` y un `unknown` no se repite.
Una dificultad es confirmada si su observación es válida y su turno no está disputado;
entonces se programa el repaso de los objetivos del escenario. "Eso no fue lo que dije" en un
turno lo marca como disputado: se ocultan sus observaciones y se registra como problema de
reconocimiento, nunca como error del alumno.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Final

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.db.uow import UnitOfWorkFactory
from app.modules.coaching.feedback import prompts
from app.modules.coaching.feedback import service as engine
from app.modules.coaching.feedback.ports import (
    EvaluatorFailed,
    EvaluatorUnknown,
    FeedbackEvaluator,
    FeedbackRequest,
)
from app.modules.coaching.service_feedback import LABEL, criteria_from
from app.modules.coaching.voice import domain, repository
from app.modules.coaching.voice.relay import session_ref
from app.modules.coaching.voice.service import _summary
from app.modules.content.service_rubrics import rubric_by_id
from app.modules.progress import service as progress_service
from app.modules.usage import domain as usage_domain
from app.modules.usage.service import CapabilityDisabled, RunView, UsageService

logger = logging.getLogger("app.coaching.voice")

PURPOSE: Final = "speaking_feedback"
MAX_OBSERVATIONS = 2


class VoiceFeedbackService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        settings: Settings,
        usage: UsageService,
        evaluator: FeedbackEvaluator | None,
    ) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings
        self.usage = usage
        self.evaluator = evaluator

    def request(self, user_id: uuid.UUID, session_id: uuid.UUID, key: str) -> dict[str, Any]:
        with self.uow() as s:
            session = repository.for_user(s, user_id, session_id)
            if session is None:
                raise NotFound()
            if session.status in repository.LIVE:
                raise Conflict("La sesión sigue abierta.", code="voice_session_open")
            if not session.save_transcript:
                return self._shown({"status": "not_evaluable", "reason": "no_consent"})
            if session.feedback is not None and session.feedback.get("status") in (
                "evaluable",
                "not_evaluable",
            ):
                return self._shown(session.feedback, session.transcript)
            transcript = list(session.transcript or [])
            speech_s = (session.learner_speech_ms or 0) / 1000
            body = repository.revision_body(s, session.scenario_revision_id)
        turns = domain.learner_turns(transcript)
        if not turns or speech_s < self.settings.voice_min_learner_speech_s:
            result = {"status": "not_evaluable", "reason": "too_little_speech", "label": LABEL}
            self._store(user_id, session_id, result, body, confirmed=False)
            return self._shown(result)
        self.usage.require("ai_feedback")
        if self.evaluator is None:
            raise CapabilityDisabled()
        same_key = self.usage.run_by_key(user_id, PURPOSE, key)
        if same_key is not None:
            if same_key.voice_session_id != session_id:
                raise Conflict("Esta clave ya se usó con otra sesión.", code="idempotency_conflict")
            return self._from_run(same_key, session_id, transcript)
        latest = self.usage.latest_for_voice_session(user_id, session_id, PURPOSE)
        if latest is not None and latest.status != "failed":
            return self._from_run(latest, session_id, transcript)
        return self._evaluate(user_id, session_id, key, body, turns, transcript)

    def _evaluate(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        key: str,
        body: dict[str, Any],
        turns: list[dict[str, Any]],
        transcript: list[dict[str, Any]],
    ) -> dict[str, Any]:
        evaluator = self.evaluator
        assert evaluator is not None
        rubric = rubric_by_id(self.settings.content_dir, str(body.get("rubric", "")))
        if rubric is None:
            # Sin rúbrica no hay criterios: no se llama al proveedor (se puede reintentar).
            logger.error("voice_feedback_rubric_missing", extra={"rubric": body.get("rubric")})
            return self._shown({"status": "failed", "reason": "rubric_missing"})
        moves = "; ".join(str(m) for m in body.get("required_moves", []))
        request = FeedbackRequest(
            kind="voice",
            prompt_version=prompts.VERSIONS["voice"],
            rubric_id=str(rubric.get("id", "")),
            rubric_version=int(rubric.get("version", 1)),
            criteria=criteria_from(rubric),
            objective_es=str(body.get("situation_es", "")),
            task_en=f"{body.get('situation_en', '')} The learner should: {moves}.",
            learner_text=" | ".join(str(t.get("text", "")) for t in turns),
            max_observations=MAX_OBSERVATIONS,
        )
        price_in = self.settings.gemini_price_input_per_mtok_microusd or 0
        price_out = self.settings.gemini_price_output_per_mtok_microusd or 0
        max_in, max_out = engine.max_tokens(prompts.render(request), evaluator)
        reservation = self.usage.reserve(
            user_id,
            purpose=PURPOSE,
            amount=usage_domain.cost_for_tokens(max_in, max_out, price_in, price_out),
            idempotency_key=key,
            provider=evaluator.provider,
            model=evaluator.model,
            prompt_version=request.prompt_version,
            rubric_version=f"{request.rubric_id}-v{request.rubric_version}",
            voice_session_id=session_id,
        )
        if reservation.existing:
            view = self.usage.run_view(reservation.run_id)
            assert view is not None
            return self._from_run(view, session_id, transcript)
        run_id = reservation.run_id
        self.usage.mark_running(run_id)
        try:
            evaluation = engine.evaluate(evaluator, request)
        except EvaluatorFailed as exc:
            self.usage.release(run_id, error_code=exc.code)
            return self._shown({"status": "failed", "reason": exc.code, "run_id": str(run_id)})
        except EvaluatorUnknown as exc:
            self.usage.mark_unknown(run_id, error_code=exc.code)
            return self._shown({"status": "unknown", "reason": exc.code, "run_id": str(run_id)})
        except Exception:
            self.usage.mark_unknown(run_id, error_code="internal_error")
            raise
        reply = evaluation.reply
        output = evaluation.feedback.as_dict()
        self.usage.settle(
            run_id,
            cost=usage_domain.cost_for_tokens(
                reply.input_tokens, reply.output_tokens, price_in, price_out
            ),
            observed_units=reply.input_tokens + reply.output_tokens,
            output=output,
            latency_ms=reply.latency_ms,
        )
        names = {c.id: c.name_es for c in criteria_from(rubric)}
        # La evidencia tiene que estar completa en un turno del alumno: una cita que cruza
        # turnos (` | `) no se puede resaltar ni disputar, y se descarta como inventada.
        observations = [
            {
                **o,
                "criterion_name_es": names.get(o["criterion"], o["criterion"]),
                "turn": domain.turn_for(o["evidence"], turns),
            }
            for o in output.get("observations", [])
        ]
        observations = [o for o in observations if o["turn"] is not None]
        status, reason = output["status"], output.get("reason")
        if status == "evaluable" and not observations:
            status, reason = "not_evaluable", "no_valid_evidence"
        result = {
            "status": status,
            "reason": reason,
            "run_id": str(run_id),
            "label": LABEL,
            "observations": observations,
            "rubric_levels": output.get("rubric_levels", {}) if status == "evaluable" else {},
        }
        shown = domain.feedback_view(result, transcript) or result
        self._store(user_id, session_id, result, body, confirmed=bool(shown["observations"]))
        return self._shown(result, transcript)

    def _store(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        result: dict[str, Any],
        body: dict[str, Any],
        *,
        confirmed: bool,
    ) -> None:
        now = self.clock.now()
        with self.uow() as s:
            session = repository.get(s, session_id, lock=True)
            if session is None or not session.save_transcript:
                return
            session.feedback = result
            if confirmed:
                # Dificultad confirmada (observación válida en un turno no disputado): se
                # repasa el objetivo del escenario como un fallo en repaso.
                progress_service.record_outcome(
                    s,
                    user_id=user_id,
                    objectives=[str(o) for o in body.get("objectives", [])],
                    outcome="incorrect",
                    aided=bool(session.aids),
                    mode="review",
                    first_attempt=False,
                    now=now,
                    intervals_hours=self.settings.review_intervals,
                )

    def _from_run(
        self, run: RunView, session_id: uuid.UUID, transcript: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if run.status in ("reserved", "running"):
            raise Conflict("El feedback anterior sigue en curso.", code="feedback_in_progress")
        with self.uow() as s:
            session = repository.get(s, session_id)
            stored = session.feedback if session is not None else None
        if run.status == "succeeded" and stored is not None:
            return self._shown(stored, transcript)
        status = "unknown" if run.status == "unknown" else "failed"
        return self._shown({"status": status, "reason": run.error_code, "run_id": str(run.id)})

    @staticmethod
    def _shown(
        feedback: dict[str, Any], transcript: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        out = domain.feedback_view({"label": LABEL, **feedback}, transcript)
        assert out is not None
        return out

    def flag_turn(self, user_id: uuid.UUID, session_id: uuid.UUID, n: int) -> dict[str, Any]:
        """ "Eso no fue lo que dije": el turno del alumno queda disputado (idempotente)."""
        with self.uow() as s:
            session = repository.for_user(s, user_id, session_id)
            if session is None:
                raise NotFound()
            turns = list(session.transcript or [])
            index = next(
                (i for i, t in enumerate(turns) if t.get("n") == n and t.get("role") == "learner"),
                None,
            )
            if index is None:
                raise ValidationFailed(
                    "Solo puedes marcar tus propios turnos.", code="voice_turn_invalid"
                )
            turns[index] = {**turns[index], "disputed": True}
            session.transcript = turns
            summary = _summary(session)
        logger.info("voice_turn_disputed", extra={"session_ref": session_ref(session_id)})
        return summary
