"""Comprobaciones (REQ-12): diagnóstico inicial y checkpoint por unidad.

- Iniciar crea una corrida con el orden de ítems fijado; si ya hay una abierta, se retoma
  (EDGE-17). El diagnóstico admite una sola corrida vigente; un admin la reinicia (EDGE-09).
  El checkpoint se repite y se numera; la primera corrida es la comparable.
- Cada respuesta se guarda al momento (`PUT`) sin feedback.
- Enviar (idempotente) corrige lo cerrado, crea un intento por ítem respondido con
  `mode = assessment` y guarda el resumen por objetivo. Las producciones quedan "no
  evaluadas automáticamente", con autoevaluación opcional.
- El DTO de la corrida va sin ayudas, transcripciones ni soluciones hasta enviar (AC-08).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.logging import user_ref
from app.db.uow import UnitOfWorkFactory
from app.modules.content import service_delivery
from app.modules.practice import domain, repository
from app.modules.practice.models import AssessmentRun, Attempt
from app.modules.practice.service import Learner, check_idempotency_key, post_submit_feedback

logger = logging.getLogger("app.practice")

START_OPERATION = "assessment_start"
SUBMIT_OPERATION = "assessment_submit"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _run_ref(run: AssessmentRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "run_number": run.run_number,
        "status": run.status,
        "comparable": run.run_number == 1,
        "started_at": run.started_at.isoformat(),
        "submitted_at": _iso(run.submitted_at),
    }


class AssessmentService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, settings: Settings) -> None:
        self.uow = uow
        self.clock = clock
        self.settings = settings

    # -- formulario -----------------------------------------------------------------------

    def _published_form(self, s: Session, form_id: uuid.UUID) -> tuple[Any, Any]:
        item = repository.item(s, form_id)
        if item is None or item.kind != "assessment_form" or item.published_revision_id is None:
            raise NotFound()
        rev = repository.revision(s, item.published_revision_id)
        if rev is None:
            raise NotFound()
        return item, rev

    def form(self, learner: Learner, form_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            item, rev = self._published_form(s, form_id)
            runs = repository.runs_for_form(s, learner.user_id, item.id)
            ref = _form_ref(s, item, rev)
            open_run = next((r for r in runs if r.status == "in_progress"), None)
            done_diagnostic = ref["form_kind"] == "initial" and any(
                r.status == "submitted" and r.reset_at is None for r in runs
            )
            return {
                **ref,
                "label": domain.FORMATIVE_LABEL,
                "runs": [_run_ref(r) for r in runs if r.reset_at is None],
                "open_run_id": str(open_run.id) if open_run else None,
                "can_start": open_run is None and not done_diagnostic,
            }

    # -- iniciar --------------------------------------------------------------------------

    def start(
        self, learner: Learner, form_id: uuid.UUID, idempotency_key: str
    ) -> tuple[int, dict[str, Any], bool]:
        key = check_idempotency_key(idempotency_key)
        body_hash = domain.request_hash({"form_id": str(form_id)})
        now = self.clock.now()
        with self.uow() as s:
            existing = repository.claim_idempotency(
                s,
                user_id=learner.user_id,
                operation=START_OPERATION,
                key=key,
                request_hash=body_hash,
                now=now,
            )
            if existing is not None:
                if existing.request_hash != body_hash:
                    raise Conflict(
                        "Esta clave ya se usó con otra comprobación.", code="idempotency_conflict"
                    )
                if existing.response is None:
                    raise Conflict(
                        "El inicio anterior sigue en curso.", code="idempotency_in_progress"
                    )
                return existing.status_code, existing.response, True

            item, rev = self._published_form(s, form_id)
            repository.lock_runs_of(s, learner.user_id, item.id)
            runs = repository.runs_for_form(s, learner.user_id, item.id)
            open_run = next((r for r in runs if r.status == "in_progress"), None)
            status = 200
            if open_run is None:
                form_kind = rev.body.get("form_kind", "checkpoint")
                if form_kind == "initial" and any(r.reset_at is None for r in runs):
                    raise Conflict(
                        "Ya hiciste el diagnóstico inicial. Si necesitas repetirlo, pídeselo al "
                        "equipo.",
                        code="diagnostic_done",
                    )
                order = [
                    str(a.id) for a in repository.activities_of(s, rev.id) if a.pool == "assessment"
                ]
                open_run = AssessmentRun(
                    id=uuid.uuid4(),
                    user_id=learner.user_id,
                    form_item_id=item.id,
                    form_revision_id=rev.id,
                    form_kind=form_kind,
                    run_number=max((r.run_number for r in runs), default=0) + 1,
                    status="in_progress",
                    item_order=order,
                    started_at=now,
                )
                s.add(open_run)
                s.flush()
                status = 201
                logger.info(
                    "assessment_started",
                    extra={
                        "user_ref": user_ref(learner.user_id, self.settings.log_salt),
                        "form_kind": form_kind,
                        "run_number": open_run.run_number,
                    },
                )
            body = self._detail(s, open_run)
            repository.store_idempotent_response(
                s,
                user_id=learner.user_id,
                operation=START_OPERATION,
                key=key,
                status=status,
                body=body,
            )
            return status, body, False

    # -- corrida --------------------------------------------------------------------------

    def run(self, learner: Learner, run_id: uuid.UUID) -> dict[str, Any]:
        with self.uow() as s:
            run = repository.run_for_user(s, learner.user_id, run_id)
            if run is None:
                raise NotFound()
            return self._detail(s, run)

    def _detail(self, s: Session, run: AssessmentRun) -> dict[str, Any]:
        item = repository.item(s, run.form_item_id)
        rev = repository.revision(s, run.form_revision_id)
        assert item is not None and rev is not None
        dto = service_delivery.item_dto(s, item, rev, mode="assessment", pools=("assessment",))
        by_id = {a["id"]: a for a in dto["activities"]}
        answers = repository.answers_of(s, run.id)
        out: dict[str, Any] = {
            **_run_ref(run),
            "form": _form_ref(s, item, rev),
            "label": domain.FORMATIVE_LABEL,
            "passages": dto.get("passages", []),
            "items": [by_id[i] for i in run.item_order if i in by_id],
            "answers": {
                str(a.activity_id): {
                    "response": a.response,
                    "audio_failed": a.audio_failed,
                    "saved_at": a.saved_at.isoformat(),
                }
                for a in answers.values()
            },
            "summary": run.summary,
            "results": [],
        }
        if run.status == "submitted":
            attempts = repository.attempts_of_run(s, run.id)
            acts = {str(a.id): a for a in repository.activities_of(s, rev.id)}
            for activity_id in run.item_order:
                act = acts.get(activity_id)
                if act is None:
                    continue
                attempt = attempts.get(act.id)
                out["results"].append(
                    {
                        "activity_id": activity_id,
                        "answered": attempt is not None,
                        "attempt_id": str(attempt.id) if attempt else None,
                        "evaluation_status": attempt.evaluation_status if attempt else None,
                        "correct": attempt.correct if attempt else None,
                        "result": attempt.result if attempt else {},
                        "feedback": post_submit_feedback(act),
                    }
                )
        return out

    # -- guardar respuesta ----------------------------------------------------------------

    def save_answer(
        self,
        learner: Learner,
        run_id: uuid.UUID,
        activity_id: uuid.UUID,
        response: dict[str, Any],
        audio_failed: bool,
    ) -> dict[str, Any]:
        now = self.clock.now()
        with self.uow() as s:
            run = repository.run_for_user(s, learner.user_id, run_id, lock=True)
            if run is None or str(activity_id) not in run.item_order:
                raise NotFound()
            if run.status != "in_progress":
                raise Conflict("Esta comprobación ya se envió.", code="run_submitted")
            found = repository.activity_with_context(s, activity_id)
            if found is None:
                raise NotFound()
            act = found[0]
            if not audio_failed:
                try:
                    domain.grade(
                        act.format, response, act.options or {}, act.solution or {}, act.rubric
                    )
                except domain.InvalidResponse as exc:
                    raise ValidationFailed(
                        f"Revisa tu respuesta: {exc}.", code="response_invalid"
                    ) from exc
            repository.upsert_answer(
                s,
                run_id=run.id,
                activity_id=act.id,
                response=response,
                audio_failed=audio_failed,
                now=now,
            )
        return {"activity_id": str(activity_id), "saved_at": now.isoformat()}

    # -- enviar ---------------------------------------------------------------------------

    def submit(
        self, learner: Learner, run_id: uuid.UUID, idempotency_key: str
    ) -> tuple[int, dict[str, Any], bool]:
        key = check_idempotency_key(idempotency_key)
        body_hash = domain.request_hash({"run_id": str(run_id)})
        now = self.clock.now()
        with self.uow() as s:
            existing = repository.claim_idempotency(
                s,
                user_id=learner.user_id,
                operation=SUBMIT_OPERATION,
                key=key,
                request_hash=body_hash,
                now=now,
            )
            if existing is not None:
                if existing.request_hash != body_hash:
                    raise Conflict(
                        "Esta clave ya se usó con otra corrida.", code="idempotency_conflict"
                    )
                if existing.response is None:
                    raise Conflict(
                        "El envío anterior sigue en curso.", code="idempotency_in_progress"
                    )
                return existing.status_code, existing.response, True

            run = repository.run_for_user(s, learner.user_id, run_id, lock=True)
            if run is None:
                raise NotFound()
            if run.status == "in_progress":
                self._grade_run(s, learner, run, now)
            body = self._detail(s, run)
            repository.store_idempotent_response(
                s,
                user_id=learner.user_id,
                operation=SUBMIT_OPERATION,
                key=key,
                status=200,
                body=body,
            )
        return 200, body, False

    def _grade_run(self, s: Session, learner: Learner, run: AssessmentRun, now: datetime) -> None:
        answers = repository.answers_of(s, run.id)
        acts = {str(a.id): a for a in repository.activities_of(s, run.form_revision_id)}
        scored: list[domain.ScoredItem] = []
        for activity_id in run.item_order:
            act = acts.get(activity_id)
            if act is None:
                continue
            answer = answers.get(act.id)
            grade: domain.Grade | None = None
            if answer is not None:
                if answer.audio_failed:
                    grade = domain.audio_not_evaluable(answer.response)
                else:
                    try:
                        grade = domain.grade(
                            act.format,
                            answer.response,
                            act.options or {},
                            act.solution or {},
                            act.rubric,
                        )
                    except domain.InvalidResponse:
                        grade = None  # una respuesta inválida guardada antes cuenta como vacía
            scored.append(
                domain.ScoredItem(
                    objectives=tuple(act.objective_codes),
                    fmt=act.format,
                    grade=grade,
                    audio_failed=bool(answer and answer.audio_failed),
                )
            )
            if grade is None or answer is None:
                continue
            s.add(
                Attempt(
                    id=uuid.uuid4(),
                    user_id=learner.user_id,
                    activity_id=act.id,
                    revision_id=run.form_revision_id,
                    mode="assessment",
                    assessment_run_id=run.id,
                    response=answer.response,
                    aids={"kinds": [], "count": 0, "audio_plays": 0},
                    evaluation_status=grade.evaluation_status,
                    evaluation_source=grade.evaluation_source,
                    score=grade.score,
                    correct=grade.correct,
                    result=grade.result,
                    is_first=run.run_number == 1,
                    submitted_at=now,
                    local_day=domain.local_day(now, learner.timezone),
                )
            )
        run.summary = domain.assessment_summary(scored)
        run.status = "submitted"
        run.submitted_at = now
        s.flush()
        logger.info(
            "assessment_submitted",
            extra={
                "user_ref": user_ref(learner.user_id, self.settings.log_salt),
                "form_kind": run.form_kind,
                "run_number": run.run_number,
            },
        )

    # -- admin ----------------------------------------------------------------------------

    def reset_diagnostic(self, admin_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """EDGE-09: el diagnóstico enviado queda en el historial con `reset_at` y el alumno
        puede hacer uno nuevo."""
        now = self.clock.now()
        with self.uow() as s:
            runs = repository.diagnostic_runs_to_reset(s, user_id)
            if not runs:
                raise NotFound("No hay un diagnóstico enviado que reiniciar.", code="no_diagnostic")
            for run in runs:
                run.reset_at = now
        logger.info(
            "diagnostic_reset",
            extra={
                "user_ref": user_ref(user_id, self.settings.log_salt),
                "by": user_ref(admin_id, self.settings.log_salt),
            },
        )
        return {"reset": len(runs)}


def _form_ref(s: Session, item: Any, rev: Any) -> dict[str, Any]:
    body = rev.body
    return {
        "id": str(item.id),
        "slug": item.slug,
        "title": body["title"],
        "form_kind": body.get("form_kind"),
        "duration_minutes": body.get("duration_minutes"),
        "unit": service_delivery.unit_ref(s, item, body),
    }
