"""Rutas de contenido para el alumno: solo rutas activas y revisiones publicadas, con DTO
de lista permitida. CS-05 suma la revisión fijada por lección."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.http.deps import AuthDep, ContainerDep
from app.modules.content.schemas import (
    ContentReportIn,
    CreatedOut,
    ItemOut,
    PathDetailOut,
    PathOut,
)
from app.modules.content.service_delivery import DeliveryService
from app.modules.content.service_editorial import EditorialService

router = APIRouter(prefix="/api/v1", tags=["content"])


def get_delivery(container: ContainerDep) -> DeliveryService:
    return DeliveryService(container.uow)


def get_editorial(container: ContainerDep) -> EditorialService:
    return EditorialService(container.uow, container.clock)


DeliveryDep = Annotated[DeliveryService, Depends(get_delivery)]
EditorialDep = Annotated[EditorialService, Depends(get_editorial)]


@router.get("/learning-paths", response_model=list[PathOut])
def list_paths(_: AuthDep, delivery: DeliveryDep) -> list[PathOut]:
    return [PathOut.model_validate(p) for p in delivery.list_paths()]


@router.get("/learning-paths/{path_id}", response_model=PathDetailOut)
def path_detail(path_id: uuid.UUID, _: AuthDep, delivery: DeliveryDep) -> PathDetailOut:
    return PathDetailOut.model_validate(delivery.path_detail(path_id))


@router.get("/scenarios/{item_id}", response_model=ItemOut)
def scenario(item_id: uuid.UUID, _: AuthDep, delivery: DeliveryDep) -> ItemOut:
    return ItemOut.model_validate(delivery.published(item_id, "scenario"))


@router.post("/content-reports", response_model=CreatedOut, status_code=201)
def report(body: ContentReportIn, ctx: AuthDep, editorial: EditorialDep) -> CreatedOut:
    report_id = editorial.report(
        user_id=ctx.user_id,
        revision_id=body.revision_id,
        activity_id=body.activity_id,
        attempt_id=body.attempt_id,
        category=body.category,
        message=body.message,
        page=body.page,
    )
    return CreatedOut(id=report_id)


@router.get("/lessons/{item_id}", response_model=ItemOut)
def lesson(item_id: uuid.UUID, _: AuthDep, delivery: DeliveryDep) -> ItemOut:
    return ItemOut.model_validate(delivery.published(item_id, "lesson"))
