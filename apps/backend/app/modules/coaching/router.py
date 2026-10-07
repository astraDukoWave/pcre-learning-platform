"""Rutas de `coaching`: feedback abierto con IA. Sin lógica."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.http.deps import AuthDep, ContainerDep
from app.modules.coaching.schemas import AiFeedbackOut
from app.modules.coaching.service_feedback import FeedbackFlowService
from app.modules.practice.service import Learner, PracticeService, check_idempotency_key
from app.modules.usage.service import UsageService

router = APIRouter(prefix="/api/v1", tags=["coaching"])


def get_feedback_flow(container: ContainerDep) -> FeedbackFlowService:
    return FeedbackFlowService(
        container.settings,
        UsageService(container.uow, container.clock, container.settings, container.provider_ready),
        PracticeService(container.uow, container.clock, container.settings),
        container.feedback_evaluator,
    )


FeedbackFlowDep = Annotated[FeedbackFlowService, Depends(get_feedback_flow)]


@router.post("/attempts/{attempt_id}/feedback", response_model=AiFeedbackOut)
def request_feedback(
    attempt_id: uuid.UUID,
    ctx: AuthDep,
    flow: FeedbackFlowDep,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", max_length=80)],
) -> AiFeedbackOut:
    learner = Learner(user_id=ctx.user_id, timezone=ctx.timezone)
    return AiFeedbackOut.model_validate(
        flow.request_feedback(learner, attempt_id, check_idempotency_key(idempotency_key))
    )
