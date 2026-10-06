"""Ruta de contenido para el alumno: reportar un problema. La entrega de rutas, lecciones y
escenarios vive en `practice` (revisión fijada y progreso propio)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.http.deps import AuthDep, ContainerDep
from app.modules.content.schemas import ContentReportIn, CreatedOut
from app.modules.content.service_editorial import EditorialService

router = APIRouter(prefix="/api/v1", tags=["content"])


def get_editorial(container: ContainerDep) -> EditorialService:
    return EditorialService(container.uow, container.clock)


EditorialDep = Annotated[EditorialService, Depends(get_editorial)]


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
