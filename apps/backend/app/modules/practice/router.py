"""Rutas de práctica del alumno. Sin lógica: validan la forma y llaman al servicio."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.http.deps import AuthDep, ContainerDep
from app.modules.identity.service import AuthContext
from app.modules.practice.schemas import (
    AidContentOut,
    AidIn,
    AttemptIn,
    AttemptOut,
    AttemptSummaryOut,
    LessonOut,
    PathOut,
    PathStateOut,
)
from app.modules.practice.service import Learner, PracticeService

router = APIRouter(prefix="/api/v1", tags=["practice"])


def get_practice(container: ContainerDep) -> PracticeService:
    return PracticeService(container.uow, container.clock, container.settings)


PracticeDep = Annotated[PracticeService, Depends(get_practice)]


def _learner(ctx: AuthContext) -> Learner:
    return Learner(user_id=ctx.user_id, timezone=ctx.timezone)


@router.get("/learning-paths", response_model=list[PathOut])
def list_paths(_: AuthDep, practice: PracticeDep) -> list[PathOut]:
    return [PathOut.model_validate(p) for p in practice.list_paths()]


@router.get("/learning-paths/{path_id}", response_model=PathStateOut)
def path_detail(path_id: uuid.UUID, ctx: AuthDep, practice: PracticeDep) -> PathStateOut:
    return PathStateOut.model_validate(practice.path_for(_learner(ctx), path_id))


@router.get("/lessons/{item_id}", response_model=LessonOut)
def lesson(item_id: uuid.UUID, ctx: AuthDep, practice: PracticeDep) -> LessonOut:
    return LessonOut.model_validate(practice.item_for(_learner(ctx), item_id, "lesson"))


@router.get("/scenarios/{item_id}", response_model=LessonOut)
def scenario(item_id: uuid.UUID, ctx: AuthDep, practice: PracticeDep) -> LessonOut:
    return LessonOut.model_validate(practice.item_for(_learner(ctx), item_id, "scenario"))


@router.post("/aids", response_model=AidContentOut)
def serve_aid(body: AidIn, ctx: AuthDep, practice: PracticeDep) -> AidContentOut:
    return AidContentOut.model_validate(
        practice.serve_aid(_learner(ctx), body.activity_id, body.kind, body.index)
    )


@router.post("/attempts", response_model=AttemptOut, status_code=201)
def submit_attempt(
    body: AttemptIn,
    ctx: AuthDep,
    practice: PracticeDep,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", max_length=80)],
) -> AttemptOut:
    status, payload, replayed = practice.submit_attempt(
        _learner(ctx),
        idempotency_key=idempotency_key,
        activity_id=body.activity_id,
        response=body.response,
        revision_of=body.revision_of,
        audio_plays=body.audio_plays,
    )
    response.status_code = status
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return AttemptOut.model_validate(payload)


@router.get("/attempts/{attempt_id}", response_model=AttemptSummaryOut)
def get_attempt(attempt_id: uuid.UUID, ctx: AuthDep, practice: PracticeDep) -> AttemptSummaryOut:
    return AttemptSummaryOut.model_validate(practice.get_attempt(_learner(ctx), attempt_id))


@router.get("/me/attempts", response_model=list[AttemptSummaryOut])
def my_attempts(
    ctx: AuthDep,
    practice: PracticeDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before: datetime | None = None,
) -> list[AttemptSummaryOut]:
    rows = practice.list_attempts(_learner(ctx), limit, before)
    return [AttemptSummaryOut.model_validate(r) for r in rows]
