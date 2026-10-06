"""Rutas de comprobaciones (REQ-12). Sin lógica: validan la forma y llaman al servicio."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from app.http.deps import AdminDep, AuthDep, ContainerDep
from app.modules.practice.router import learner_from
from app.modules.practice.schemas import (
    AnswerIn,
    AnswerSavedOut,
    AssessmentFormOut,
    AssessmentRunOut,
    DiagnosticResetOut,
)
from app.modules.practice.service_assessment import AssessmentService

router = APIRouter(prefix="/api/v1", tags=["assessment"])


def get_assessments(container: ContainerDep) -> AssessmentService:
    return AssessmentService(container.uow, container.clock, container.settings)


AssessmentDep = Annotated[AssessmentService, Depends(get_assessments)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", max_length=80)]


@router.get("/assessments/{form_id}", response_model=AssessmentFormOut)
def form(form_id: uuid.UUID, ctx: AuthDep, svc: AssessmentDep) -> AssessmentFormOut:
    return AssessmentFormOut.model_validate(svc.form(learner_from(ctx), form_id))


@router.post("/assessments/{form_id}/start", response_model=AssessmentRunOut, status_code=201)
def start(
    form_id: uuid.UUID,
    ctx: AuthDep,
    svc: AssessmentDep,
    response: Response,
    idempotency_key: IdempotencyKey,
) -> AssessmentRunOut:
    status, body, replayed = svc.start(learner_from(ctx), form_id, idempotency_key)
    response.status_code = status
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return AssessmentRunOut.model_validate(body)


@router.get("/assessment-runs/{run_id}", response_model=AssessmentRunOut)
def run(run_id: uuid.UUID, ctx: AuthDep, svc: AssessmentDep) -> AssessmentRunOut:
    return AssessmentRunOut.model_validate(svc.run(learner_from(ctx), run_id))


@router.put("/assessment-runs/{run_id}/answers/{activity_id}", response_model=AnswerSavedOut)
def save_answer(
    run_id: uuid.UUID, activity_id: uuid.UUID, body: AnswerIn, ctx: AuthDep, svc: AssessmentDep
) -> AnswerSavedOut:
    saved = svc.save_answer(
        learner_from(ctx), run_id, activity_id, body.response, body.audio_failed
    )
    return AnswerSavedOut.model_validate(saved)


@router.post("/assessment-runs/{run_id}/submit", response_model=AssessmentRunOut)
def submit(
    run_id: uuid.UUID,
    ctx: AuthDep,
    svc: AssessmentDep,
    response: Response,
    idempotency_key: IdempotencyKey,
) -> AssessmentRunOut:
    status, body, replayed = svc.submit(learner_from(ctx), run_id, idempotency_key)
    response.status_code = status
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return AssessmentRunOut.model_validate(body)


@router.post("/admin/users/{user_id}/diagnostic-reset", response_model=DiagnosticResetOut)
def reset_diagnostic(user_id: uuid.UUID, ctx: AdminDep, svc: AssessmentDep) -> DiagnosticResetOut:
    return DiagnosticResetOut.model_validate(svc.reset_diagnostic(ctx.user_id, user_id))
