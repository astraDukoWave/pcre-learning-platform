"""Rutas de `insights`: feedback del alumno y panel del piloto (solo admin). Sin lógica."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.http.deps import AdminDep, AuthDep, ContainerDep
from app.modules.insights.schemas import (
    CreatedOut,
    ErrorRowOut,
    FeedbackIn,
    FeedbackOverviewOut,
    PilotSummaryOut,
)
from app.modules.insights.service import InsightsService

router = APIRouter(prefix="/api/v1", tags=["insights"])


def get_insights(container: ContainerDep) -> InsightsService:
    return InsightsService(container.uow, container.clock)


InsightsDep = Annotated[InsightsService, Depends(get_insights)]


@router.post("/feedback", response_model=CreatedOut, status_code=201)
def submit_feedback(body: FeedbackIn, ctx: AuthDep, svc: InsightsDep) -> CreatedOut:
    feedback_id = svc.submit_feedback(
        ctx.user_id,
        context_type=body.context_type,
        context_id=body.context_id,
        rating=body.rating,
        message=body.message,
        page=body.page,
        observation=body.observation,
    )
    return CreatedOut(id=feedback_id)


@router.get("/admin/pilot/summary", response_model=PilotSummaryOut)
def pilot_summary(
    _: AdminDep, svc: InsightsDep, days: Annotated[int, Query(ge=1, le=28)] = 7
) -> PilotSummaryOut:
    return PilotSummaryOut.model_validate(svc.pilot_summary(days))


@router.get("/admin/feedback", response_model=FeedbackOverviewOut)
def feedback_overview(_: AdminDep, svc: InsightsDep) -> FeedbackOverviewOut:
    return FeedbackOverviewOut.model_validate(svc.feedback_overview())


@router.get("/admin/errors", response_model=list[ErrorRowOut])
def errors(
    _: AdminDep, svc: InsightsDep, days: Annotated[int, Query(ge=1, le=30)] = 30
) -> list[ErrorRowOut]:
    return [ErrorRowOut.model_validate(e) for e in svc.errors(days)]
