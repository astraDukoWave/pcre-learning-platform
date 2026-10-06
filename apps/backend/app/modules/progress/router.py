"""Rutas de progreso y repasos del alumno. Sin lógica: llaman al servicio."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.http.deps import AuthDep, ContainerDep
from app.modules.identity.service import AuthContext
from app.modules.progress.schemas import LearnerProgressOut, ReviewsOut
from app.modules.progress.service import ProgressService, Viewer

router = APIRouter(prefix="/api/v1", tags=["progress"])


def get_progress(container: ContainerDep) -> ProgressService:
    return ProgressService(container.uow, container.clock, container.settings)


ProgressDep = Annotated[ProgressService, Depends(get_progress)]


def _viewer(ctx: AuthContext) -> Viewer:
    return Viewer(user_id=ctx.user_id, timezone=ctx.timezone)


@router.get("/me/progress", response_model=LearnerProgressOut)
def my_progress(ctx: AuthDep, svc: ProgressDep) -> LearnerProgressOut:
    return LearnerProgressOut.model_validate(svc.progress(_viewer(ctx)))


@router.get("/me/reviews", response_model=ReviewsOut)
def my_reviews(ctx: AuthDep, svc: ProgressDep) -> ReviewsOut:
    return ReviewsOut.model_validate(svc.reviews(_viewer(ctx)))
