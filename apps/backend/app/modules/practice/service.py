"""Casos de uso de práctica (REQ-09, REQ-11): recorrido con estado por lección, revisión
fijada, ayudas servidas por el servidor e intentos idempotentes.

Un intento, su registro de idempotencia, el enlace de las ayudas, el progreso de la
lección y el repaso se escriben en una sola transacción.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.logging import user_ref
from app.db.uow import UnitOfWorkFactory
from app.modules.content import service_delivery
from app.modules.content.service_delivery import DeliveryService
from app.modules.practice import domain, repository
from app.modules.practice.models import Attempt, LessonProgress, ServedAid
from app.modules.progress import service as progress_service

logger = logging.getLogger("app.practice")

ATTEMPT_OPERATION = "attempt"
WITHDRAWN_NOTICE = "Esta lección se retiró para corregirla. Tus respuestas se conservan."


@dataclass(frozen=True)
class Learner:
    user_id: uuid.UUID
    timezone: str


def _attempt_summary(a: Attempt) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "activity_id": str(a.activity_id),
        "response": a.response,
        "evaluation_status": a.evaluation_status,
        "score": a.score,
        "correct": a.correct,
        "result": a.result,
        "aided": bool(a.aids.get("kinds")),
        "submitted_at": a.submitted_at.isoformat(),
    }


class PracticeService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, settings: Settings) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings

    # -- recorrido ------------------------------------------------------------------------

    def list_paths(self) -> list[dict[str, Any]]:
        return DeliveryService(self.uow).list_paths()

    def path_for(self, learner: Learner, path_id: uuid.UUID) -> dict[str, Any]:
        detail = DeliveryService(self.uow).path_detail(path_id)
        with self.uow() as s:
            path = repository.path(s, path_id)
            assert path is not None
            repository.ensure_enrollment(s, learner.user_id, path, self.clock.now())
            progress = repository.progress_by_item(s, learner.user_id)
            runs = repository.run_states(s, learner.user_id)
        for unit in detail["units"]:
            for item in unit["items"]:
                item_id = uuid.UUID(item["id"])
                if item["kind"] == "assessment_form":
                    item["state"] = runs.get(item_id, "not_started")
                else:
                    item["state"] = _state(progress.get(item_id))
        for item in detail["assessments"]:
            item["state"] = runs.get(uuid.UUID(item["id"]), "not_started")
        return detail

    def _accessible_revision(
        self, s: Session, learner: Learner, item_id: uuid.UUID, *, pin: bool
    ) -> tuple[Any, Any, LessonProgress | None, str | None]:
        """Revisión fijada si la lección está en curso; si no, la publicada (EDGE-04).
        Si la fijada se retiró, se libera (EDGE-05)."""
        item = repository.item(s, item_id)
        if item is None or item.kind not in ("lesson", "scenario"):
            raise NotFound()
        progress = repository.progress_for(s, learner.user_id, item.id, lock=pin)
        notice = None
        rev = None
        if progress is not None and progress.completed_at is None and progress.pinned_revision_id:
            pinned = repository.revision(s, progress.pinned_revision_id)
            if pinned is not None and pinned.status != "withdrawn":
                rev = pinned
            else:
                notice = WITHDRAWN_NOTICE
                progress.pinned_revision_id = None
        if rev is None:
            if item.published_revision_id is None:
                if notice:
                    raise NotFound(WITHDRAWN_NOTICE, code="lesson_withdrawn")
                raise NotFound()
            rev = repository.revision(s, item.published_revision_id)
            if rev is None:
                raise NotFound()
            if pin:
                now = self.clock.now()
                if progress is None:
                    progress = LessonProgress(
                        id=uuid.uuid4(),
                        user_id=learner.user_id,
                        item_id=item.id,
                        pinned_revision_id=rev.id,
                        started_at=now,
                    )
                    s.add(progress)
                    logger.info("lesson_started", extra={"item_id": str(item.id)})
                elif progress.completed_at is None:
                    progress.pinned_revision_id = rev.id
        return item, rev, progress, notice

    def item_for(self, learner: Learner, item_id: uuid.UUID, kind: str) -> dict[str, Any]:
        with self.uow() as s:
            item, rev, progress, notice = self._accessible_revision(s, learner, item_id, pin=True)
            if item.kind != kind:
                raise NotFound()
            dto = service_delivery.item_dto(s, item, rev)
            last = repository.last_attempts_by_key(s, learner.user_id, item.id)
            by_key = {a["key"]: a for a in dto["activities"]}
            dto["last_attempts"] = {
                by_key[key]["id"]: _attempt_summary(attempt)
                for key, attempt in last.items()
                if key in by_key
            }
            dto["notice"] = notice
            dto["progress"] = {
                "started_at": progress.started_at.isoformat() if progress else None,
                "completed_at": progress.completed_at.isoformat()
                if progress and progress.completed_at
                else None,
            }
            return dto

    # -- ayudas ---------------------------------------------------------------------------

    def serve_aid(
        self, learner: Learner, activity_id: uuid.UUID, kind: str, index: int
    ) -> dict[str, Any]:
        if kind not in domain.AID_KINDS:
            raise ValidationFailed("Ayuda desconocida.", code="aid_invalid")
        with self.uow() as s:
            found = repository.activity_with_context(s, activity_id)
            if found is None:
                raise NotFound()
            act, rev, item = found
            self._check_access(s, learner, act, rev, item)
            if act.pool == "assessment":
                raise Forbidden(
                    "Las ayudas están desactivadas en una comprobación.", code="assessment_mode"
                )
            content: str | None = None
            if kind == "hint":
                content = act.hints[index] if 0 <= index < len(act.hints) else None
            elif kind == "support_es":
                content = act.support_es
            elif kind == "transcript":
                content = act.transcript
            elif kind == "example":
                content = act.example
            if not content:
                raise NotFound("Esta actividad no tiene esa ayuda.", code="aid_unavailable")
            s.add(
                ServedAid(
                    id=uuid.uuid4(),
                    user_id=learner.user_id,
                    activity_id=act.id,
                    kind=kind,
                    index=index,
                    served_at=self.clock.now(),
                )
            )
        logger.info("aid_used", extra={"kind": kind, "activity_id": str(activity_id)})
        remaining = max(0, len(act.hints) - index - 1) if kind == "hint" else 0
        return {"kind": kind, "index": index, "content": content, "remaining": remaining}

    def _check_access(self, s: Session, learner: Learner, act: Any, rev: Any, item: Any) -> None:
        """La actividad pertenece a una revisión accesible: publicada o fijada por el alumno."""
        if rev.status == "withdrawn":
            raise NotFound(WITHDRAWN_NOTICE, code="lesson_withdrawn")
        if item.published_revision_id == rev.id:
            return
        progress = repository.progress_for(s, learner.user_id, item.id)
        if progress is not None and progress.pinned_revision_id == rev.id:
            return
        raise NotFound()

    # -- intentos -------------------------------------------------------------------------

    def submit_attempt(
        self,
        learner: Learner,
        *,
        idempotency_key: str,
        activity_id: uuid.UUID,
        response: dict[str, Any],
        revision_of: uuid.UUID | None,
        audio_plays: int,
    ) -> tuple[int, dict[str, Any], bool]:
        """Devuelve (status, cuerpo, repetido). Misma clave y mismo cuerpo → misma
        respuesta y una sola fila; misma clave y cuerpo distinto → 409 (AC-09)."""
        key = check_idempotency_key(idempotency_key)
        body_hash = domain.request_hash(
            {
                "activity_id": str(activity_id),
                "response": response,
                "revision_of": str(revision_of) if revision_of else None,
                "audio_plays": audio_plays,
            }
        )
        now = self.clock.now()
        with self.uow() as s:
            existing = repository.claim_idempotency(
                s,
                user_id=learner.user_id,
                operation=ATTEMPT_OPERATION,
                key=key,
                request_hash=body_hash,
                now=now,
            )
            if existing is not None:
                if existing.request_hash != body_hash:
                    raise Conflict(
                        "Esta clave ya se usó con otra respuesta.", code="idempotency_conflict"
                    )
                if existing.response is None:
                    raise Conflict(
                        "El envío anterior sigue en curso.", code="idempotency_in_progress"
                    )
                return existing.status_code, existing.response, True

            body = self._create_attempt(
                s, learner, activity_id, response, revision_of, audio_plays, now
            )
            repository.store_idempotent_response(
                s,
                user_id=learner.user_id,
                operation=ATTEMPT_OPERATION,
                key=key,
                status=201,
                body=body,
            )
        logger.info(
            "attempt_submitted",
            extra={
                "user_ref": user_ref(learner.user_id, self.settings.log_salt),
                "mode": body["mode"],
                "evaluation_status": body["evaluation_status"],
            },
        )
        return 201, body, False

    def _create_attempt(
        self,
        s: Session,
        learner: Learner,
        activity_id: uuid.UUID,
        response: dict[str, Any],
        revision_of: uuid.UUID | None,
        audio_plays: int,
        now: datetime,
    ) -> dict[str, Any]:
        found = repository.activity_with_context(s, activity_id)
        if found is None:
            raise NotFound()
        act, rev, item = found
        self._check_access(s, learner, act, rev, item)
        if act.pool == "assessment":
            raise Forbidden(
                "Las respuestas de una comprobación se guardan en su corrida.",
                code="assessment_mode",
            )
        if revision_of is not None:
            previous = repository.attempt_for_user(s, learner.user_id, revision_of)
            if previous is None or previous.activity_id != act.id:
                raise NotFound()
        try:
            grade = domain.grade(
                act.format, response, act.options or {}, act.solution or {}, act.rubric
            )
        except domain.InvalidResponse as exc:
            raise ValidationFailed(f"Revisa tu respuesta: {exc}.", code="response_invalid") from exc

        aids = repository.unlinked_aids(s, learner.user_id, act.id)
        aid_kinds = sorted({a.kind for a in aids})
        first = (
            repository.prior_attempts_for_key(s, learner.user_id, item.id, act.activity_key) == 0
        )
        mode = act.pool
        attempt = Attempt(
            id=uuid.uuid4(),
            user_id=learner.user_id,
            activity_id=act.id,
            revision_id=rev.id,
            mode=mode,
            revision_of=revision_of,
            response=response,
            aids={"kinds": aid_kinds, "count": len(aids), "audio_plays": audio_plays},
            evaluation_status=grade.evaluation_status,
            evaluation_source=grade.evaluation_source,
            score=grade.score,
            correct=grade.correct,
            result=grade.result,
            is_first=first,
            submitted_at=now,
            local_day=domain.local_day(now, learner.timezone),
        )
        s.add(attempt)
        s.flush()
        for aid in aids:
            aid.attempt_id = attempt.id

        completed = self._update_lesson_progress(s, learner, item, rev, now)

        review_objectives: list[str] = []
        if grade.correct is not None and mode in ("practice", "review"):
            review_objectives = progress_service.record_outcome(
                s,
                user_id=learner.user_id,
                objectives=list(act.objective_codes),
                outcome="correct" if grade.correct else "incorrect",
                aided=bool(aid_kinds),
                mode=mode,  # type: ignore[arg-type]
                first_attempt=first,
                now=now,
                intervals_hours=self.settings.review_intervals,
            )
        return {
            "id": str(attempt.id),
            "activity_id": str(act.id),
            "revision_id": str(rev.id),
            "mode": mode,
            "evaluation_status": grade.evaluation_status,
            "evaluation_source": grade.evaluation_source,
            "score": grade.score,
            "correct": grade.correct,
            "result": grade.result,
            "aided": bool(aid_kinds),
            "first_attempt": first,
            "submitted_at": now.isoformat(),
            "feedback": post_submit_feedback(act),
            "lesson_completed": completed,
            "review_objectives": review_objectives,
        }

    def _update_lesson_progress(
        self, s: Session, learner: Learner, item: Any, rev: Any, now: datetime
    ) -> bool | None:
        if item.kind not in ("lesson", "scenario"):
            return None
        progress = repository.progress_for(s, learner.user_id, item.id, lock=True)
        if progress is None:
            progress = LessonProgress(
                id=uuid.uuid4(),
                user_id=learner.user_id,
                item_id=item.id,
                pinned_revision_id=rev.id,
                started_at=now,
            )
            s.add(progress)
            s.flush()
        if progress.completed_at is not None:
            return True
        practice_ids = {a.id for a in repository.activities_of(s, rev.id) if a.pool == "practice"}
        attempted = repository.attempted_activity_ids(s, learner.user_id, rev.id)
        if domain.lesson_completed({str(i) for i in practice_ids}, {str(i) for i in attempted}):
            progress.completed_at = now
            logger.info("lesson_completed", extra={"item_id": str(item.id)})
            return True
        return False

    def self_assess(
        self, learner: Learner, attempt_id: uuid.UUID, scores: dict[str, Any]
    ) -> dict[str, Any]:
        """Cierra una producción `pending` con la autoevaluación del alumno. Repetir con las
        mismas marcas devuelve lo mismo; con otras marcas, 409: para cambiar de opinión se
        reformula (intento nuevo con `revision_of`)."""
        with self.uow() as s:
            attempt = repository.attempt_for_user(s, learner.user_id, attempt_id, lock=True)
            if attempt is None:
                raise NotFound()
            found = repository.activity_with_context(s, attempt.activity_id)
            if found is None:
                raise NotFound()
            act = found[0]
            if attempt.evaluation_status == "evaluated" and attempt.evaluation_source == "self":
                if attempt.result.get("self_assessment") == scores:
                    return _attempt_detail(attempt, act)
                raise Conflict(
                    "Ya autoevaluaste este intento. Reformula para intentarlo de nuevo.",
                    code="already_assessed",
                )
            try:
                grade = domain.self_assess(
                    act.format, attempt.evaluation_status, attempt.result, scores, act.rubric
                )
            except domain.InvalidResponse as exc:
                raise ValidationFailed(
                    f"Revisa tu autoevaluación: {exc}.", code="self_assessment_invalid"
                ) from exc
            attempt.evaluation_status = grade.evaluation_status
            attempt.score = grade.score
            attempt.result = grade.result
            s.flush()
            out = _attempt_detail(attempt, act)
        logger.info(
            "self_assessed",
            extra={"user_ref": user_ref(learner.user_id, self.settings.log_salt)},
        )
        return out

    def get_attempt(self, learner: Learner, attempt_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            attempt = repository.attempt_for_user(s, learner.user_id, attempt_id)
            if attempt is None:
                raise NotFound()
            found = repository.activity_with_context(s, attempt.activity_id)
            if found is None:
                raise NotFound()
            return _attempt_detail(attempt, found[0])

    def list_attempts(
        self, learner: Learner, limit: int, before: datetime | None
    ) -> list[dict[str, Any]]:
        with self.uow() as s:
            rows = repository.recent_attempts(s, learner.user_id, limit, before)
            return [_attempt_summary(a) | {"mode": a.mode} for a in rows]


def _attempt_detail(attempt: Attempt, act: Any) -> dict[str, Any]:
    """Un intento propio ya enviado con lo que se muestra después de enviar (retomar la
    autoevaluación después de recargar). Las comprobaciones (CS-07) no pasan por aquí."""
    return _attempt_summary(attempt) | {"mode": attempt.mode, "feedback": post_submit_feedback(act)}


def _state(progress: LessonProgress | None) -> str:
    if progress is None:
        return "not_started"
    return "completed" if progress.completed_at else "in_progress"


def post_submit_feedback(act: Any) -> dict[str, Any]:
    """Lo que se muestra después de enviar: explicación, clave y, en producciones, el
    ejemplo comentado y la rúbrica para la autoevaluación."""
    solution = act.solution or {}
    out: dict[str, Any] = {"explanation": act.explanation}
    if act.format in ("short_writing", "recorded_speaking"):
        out.update(
            {
                "model_answer": solution.get("model_answer"),
                "model_commentary_es": solution.get("model_commentary_es"),
                "target_sentence": solution.get("target_sentence"),
                "rubric": act.rubric,
            }
        )
    return out


def check_idempotency_key(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationFailed(
            "Falta la clave de idempotencia (Idempotency-Key, un UUID).", code="idempotency_key"
        ) from exc
